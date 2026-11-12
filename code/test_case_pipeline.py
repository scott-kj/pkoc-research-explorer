"""Engineering tests: no real model, paid calls, or new research dataset."""
from __future__ import annotations
import copy
import hashlib
import json
import os
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from case_pipeline.common import ROOT, RunStore, digest, file_hash, read_json, validate_schema, write_json
from case_pipeline.ingest import inventory, prepare, read_catalog, validate_case
from case_pipeline.inference import ground, inference, make_bundle
from case_pipeline.providers import (BudgetExhausted, CompatibleBackend, LocalBackend, RequestStore,
                                     runtime_receipt, safe_endpoint, validate_provider)
from case_pipeline.runner import execute, parser, validate_run
from inference_components import disposition, retrieve


def case_profile(limit=None):
    return {'schema_version': 'pkoc-case-v1', 'case_id': 'fixture', 'title': 'Fictional engineering fixture',
            'mission': {'name': 'TEST', 'aliases': ['Test Mission'], 'language': 'en'},
            'documents': [{'symbol': 'S/2000/13', 'include': True, 'eligibility_reason': 'fictional engineering test'}],
            'cleaning': {'mode': 'numbered', 'truncate_annex': True, 'stop_headings': [], 'paragraph_limit': limit}}


def provider_profile(endpoint='http://127.0.0.1:1/v1'):
    stages = {s: {'input_ceiling': 50000, 'max_tokens': 1024, 'context_size': 65536,
                  'token_margin': 256, 'temperature': 0} for s in ('extraction', 'resolution', 'offices', 'cameo')}
    return {'schema_version': 'pkoc-provider-v1', 'backend': 'openai-compatible', 'model': 'fixture',
            'endpoint': endpoint, 'api_key_env': 'PKOC_TEST_KEY',
            'capabilities': {'json_schema': True, 'seed': False, 'thinking': False,
                             'tokenization': 'declared-upper-bound', 'tokens_per_utf8_byte_upper_bound': 1,
                             'chat_overhead_tokens': 128}, 'stages': stages, 'max_attempts': 2, 'timeout_seconds': 5}


def fixture_reply(body):
    stage = body['response_format']['json_schema']['name'].removeprefix('pkoc_')
    content = body['messages'][1]['content']
    packet = json.loads(content.split('SOURCE_PACKET_JSON:\n', 1)[1].split('\nRESPONSE_SCHEMA_JSON:', 1)[0])
    result = {'request_id': packet['request_id']}
    if stage == 'extraction':
        result['segments'] = []
        for s in packet['segments']:
            occurrences = []
            for name in ('Orin Kelm', 'Lina Daro'):
                start = 0
                while (start := s['text'].find(name, start)) >= 0:
                    occurrences.append({'text': name, 'left_context': s['text'][max(0, start - 14):start] or None,
                                        'right_context': None})
                    start += len(name)
            result['segments'].append({'segment_id': s['segment_id'], 'status': 'complete',
                                       'occurrences': occurrences, 'missing_context': []})
    elif stage == 'resolution':
        result['relations'] = [{'candidate_id': c['candidate_id'], 'decision': 'SAME' if packet['target']['surface'] in c['names'] else 'DIFFERENT',
                                'evidence_conflict': False, 'evidence_ids': [e['evidence_id'] for e in packet['evidence']],
                                'reason': 'Fictional controlled fixture'} for c in packet['candidates']]
    elif stage == 'offices':
        ids = [e['evidence_id'] for e in packet['evidence'] if 'Governor' in e['text']]
        result.update(person_id=packet['person']['person_id'], status='SUPPORTED' if ids else 'INSUFFICIENT',
                      claims=[{'claim_id': 'c1', 'role_literal': 'Governor', 'office_literal': 'Governor',
                               'affiliation_literal': None, 'capacity_status': 'current', 'evidence_ids': ids}] if ids else [],
                      reason='Fictional controlled fixture')
    else:
        result.update(person_id=packet['person']['person_id'], assignments=[{
            'claim_id': c['claim_id'], 'status': 'SUPPORTED', 'role_codes': ['GOV'], 'specialty_codes': [],
            'evidence_ids': c['evidence_ids'], 'reason': 'Fictional controlled fixture',
            **{k: c[k] for k in ('role_literal', 'office_literal', 'affiliation_literal')}} for c in packet['claims']])
    return {'model': 'fixture', 'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(result)}}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70}}


class FakeBackend:
    def __init__(self, profile=None, responder=fixture_reply):
        self.profile = profile or provider_profile()
        self.secrets = ('test-secret',)
        self.calls = []
        self.responder = responder
    def payload(self, stage, messages, schema):
        return {'messages': messages, 'response_format': {'json_schema': {'name': 'pkoc_' + stage}},
                'model': 'fixture'}, {'input_tokens': 1, 'input_measurement': 'controlled-fixture'}
    def complete(self, body):
        self.calls.append(body)
        return self.responder(body)


@contextmanager
def server_fixture(port=0):
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def respond(self, value):
            raw = json.dumps(value).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            seen.append({'path': self.path, 'authorization': self.headers.get('Authorization')})
            self.respond({'status': 'ok'} if self.path == '/health' else {'data': [{'id': 'fixture'}]})
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            seen.append({'path': self.path, 'body': body, 'authorization': self.headers.get('Authorization')})
            if self.path == '/apply-template':
                self.respond({'prompt': json.dumps(body['messages'])})
            elif self.path == '/tokenize':
                self.respond({'tokens': list(range(10))})
            else:
                self.respond(fixture_reply(body))
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server, seen
    finally:
        server.shutdown(); server.server_close(); worker.join(3)


class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.sources = self.root / 'sources'; self.sources.mkdir()
        self.file = self.sources / 'S_2000_13_E.pdf.txt'
        self.file.write_text('United Nations S/2000/13\n11 January 2000\n1. Governor Orin Kelm met Lina Daro. Orin Kelm left.\n2. No named people here.\nAnnex\nNot selected.\n', encoding='utf8')
        self.case = case_profile()
    def tearDown(self):
        self.temp.cleanup()
    def prepared(self):
        inv = inventory(self.case, self.sources)
        return inv, prepare(self.case, self.sources, inv)
    def test_duplicate_catalog_headers_ignore_bad_filename(self):
        catalog = self.root / 'metadata.csv'
        catalog.write_text('Mission name,Document_ID,Document_ID,Year ,Month,\nTEST,S/2000/13,S_2000_13,2000,January,WRONG.pdf.txt\n')
        rows, warnings = read_catalog(catalog)
        self.assertTrue(warnings)
        inv = inventory(self.case, self.sources, catalog)
        self.assertEqual(inv['reports'][0]['source_file'], self.file.name)
        self.assertEqual(inv['reports'][0]['report_date'], '2000-01-11')
    def test_wrong_header_and_duplicate_file_rejected(self):
        self.file.write_text('S/2000/99\n11 January 2000\n1. Text.')
        with self.assertRaisesRegex(ValueError, 'header symbol'):
            inventory(self.case, self.sources)
        self.file.write_text('S/2000/13\n1. Text.')
        (self.sources / 'S_2000_13_E.txt').write_bytes(self.file.read_bytes())
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            inventory(self.case, self.sources)
    def test_catalog_mission_and_dates_mismatch(self):
        catalog = self.root / 'metadata.csv'
        catalog.write_text('Mission name,Document_ID,Year,Month\nOTHER,S/2000/13,2000,January\n')
        with self.assertRaisesRegex(ValueError, 'mission conflicts'):
            inventory(self.case, self.sources, catalog)
        catalog.write_text('Mission name,Document_ID,Year,Month\nTEST,S/2000/13,2000,February\n')
        with self.assertRaisesRegex(ValueError, 'date mismatch'):
            inventory(self.case, self.sources, catalog)
    def test_partial_unknown_dates_and_txt_filename(self):
        self.file.rename(self.sources / 'S_2000_13_E.txt')
        self.file = self.sources / 'S_2000_13_E.txt'
        self.file.write_text('S/2000/13\nJanuary 2000\n1. Text.')
        self.case['documents'][0]['report_date'] = '2000-01-11'
        self.assertEqual(inventory(self.case, self.sources)['reports'][0]['report_date'], '2000-01')
        self.file.write_text('S/2000/13\n1. Text.')
        self.assertIsNone(inventory(self.case, self.sources)['reports'][0]['report_date'])
    def test_case_selection_and_language_not_inferred(self):
        self.case['mission']['language'] = 'fr'
        with self.assertRaisesRegex(ValueError, 'English'):
            validate_case(self.case)
        self.case['mission']['language'] = 'en'
        self.case['documents'][0]['include'] = False
        with self.assertRaisesRegex(ValueError, 'At least one'):
            inventory(self.case, self.sources)
    def test_mapped_cleaning_unicode_and_limit(self):
        self.file.write_text('S/2000/13\n11 January 2000\n1. 😀 Rene\u0301 Daro’s office.\n2. Second paragraph.\nAnnex\nPrivate annex text.', encoding='utf8')
        self.case['cleaning']['paragraph_limit'] = 1
        inv, prepared = self.prepared()
        p = prepared['paragraphs'][0]
        self.assertEqual(p['text'], "😀 René Daro's office.")
        self.assertEqual(len(p['text']), len(p['source_codepoint_spans']))
        self.assertEqual(prepared['cleaning'][0]['excluded_by_limit'], 1)
        self.assertNotIn('Annex', p['text'])
    def test_exact_unicode_grounding_and_ambiguous_anchors(self):
        text = '😀 René met René.'
        self.assertEqual(ground(text, {'text': 'René', 'left_context': '😀 ', 'right_context': None}), (2, 6, 'exact'))
        self.assertEqual(ground(text, {'text': 'René', 'left_context': None, 'right_context': None}), (None, None, 'ambiguous'))
        self.assertEqual(ground(text, {'text': 'Rene', 'left_context': None, 'right_context': None})[2], 'unmatched')
    def test_ambiguity_never_first_same_and_short_name_abstains(self):
        rel = [{'candidate_id': p, 'decision': 'SAME', 'evidence_conflict': False} for p in ('a', 'b')]
        self.assertIsNone(disposition('Orin Kelm', rel)['person_id'])
        self.assertEqual(disposition('Kelm', [])['status'], 'unresolved')
        people = {'a': {'names': ['Orin Kelm']}, 'b': {'names': ['Orin Kelm']}}
        self.assertEqual(len(retrieve('Orin Kelm', people)), 2)
    def test_full_adaptive_fixture_and_projection_deduplicates(self):
        inv, prepared = self.prepared()
        backend = FakeBackend()
        ledger = inference(self.case, prepared, RequestStore(self.root / 'requests', backend, 100))
        self.assertEqual(ledger['status']['status'], 'complete')
        self.assertEqual(len(ledger['nodes']), 2)
        self.assertEqual(ledger['coverage'][1]['status'], 'processed_empty')
        bundle = make_bundle(self.case, inv, prepared, ledger, 'a' * 64)
        self.assertEqual(bundle['dataset']['rosters'], ['L'])
        self.assertTrue(all(n['summary']['edges'] == 1 for n in bundle['networks']))
        self.assertTrue(all(n['edges'][0]['weight'] == 1 for n in bundle['networks']))
        self.assertNotIn('raw_anchor', json.dumps(bundle))
        self.assertNotIn('Fictional controlled fixture', json.dumps(bundle))
        self.assertNotIn(prepared['paragraphs'][0]['text'], json.dumps(bundle))
    def test_valid_empty_is_not_failure_and_failure_is_not_empty(self):
        self.file.write_text('S/2000/13\n1. No named people here.')
        inv, prepared = self.prepared()
        ledger = inference(self.case, prepared, RequestStore(self.root / 'empty', FakeBackend(), 5))
        self.assertEqual(ledger['coverage'][0]['status'], 'processed_empty')
        def failed(body):
            return {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]}
        ledger = inference(self.case, prepared, RequestStore(self.root / 'failed', FakeBackend(responder=failed), 5))
        self.assertEqual(ledger['coverage'][0]['status'], 'failed_or_context_excluded')
        self.assertEqual(ledger['status']['attempts'], 2)
        self.assertEqual(ledger['status']['status'], 'complete_with_failures')
    def test_budget_resume_and_input_mismatch(self):
        inv, prepared = self.prepared()
        requests = self.root / 'bounded'
        first = inference(self.case, prepared, RequestStore(requests, FakeBackend(), 1))
        self.assertEqual(first['status']['status'], 'partial')
        backend = FakeBackend()
        second = inference(self.case, prepared, RequestStore(requests, backend, 1))
        self.assertEqual(second['status']['status'], 'partial')
        self.assertEqual(len(backend.calls), 0)
        path = next(requests.glob('*.start.json'))
        record = read_json(path); record['request']['model'] = 'tampered'; write_json(path, record)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            RequestStore(requests, FakeBackend(), 1)
    def test_interrupted_attempt_counts_and_only_one_retry(self):
        def interrupted(body):
            raise KeyboardInterrupt()
        _, prepared = self.prepared()
        requests = self.root / 'interrupted'
        ledger = inference(self.case, prepared, RequestStore(requests, FakeBackend(responder=interrupted), 1))
        self.assertEqual(ledger['status']['status'], 'interrupted')
        self.assertEqual(len(list(requests.glob('*.start.json'))), 1)
        self.assertEqual(len(list(requests.glob('*.finish.json'))), 0)
        ledger = inference(self.case, prepared, RequestStore(requests, FakeBackend(), 1))
        self.assertEqual(ledger['status']['status'], 'partial')
    def test_output_protection_resume_and_separate_runs(self):
        binding = {'inputs': 'one'}
        path = self.root / 'run'
        with RunStore(path, binding) as run:
            run.write('sample.json', {'x': 1})
        with self.assertRaisesRegex(ValueError, 'new/empty'):
            RunStore(path, binding)
        with self.assertRaisesRegex(ValueError, 'changed'):
            RunStore(path, {'inputs': 'two'}, resume=True)
        with RunStore(path, binding, resume=True) as run:
            self.assertEqual(run.state['artifacts']['sample.json'], file_hash(path / 'sample.json'))
        with RunStore(self.root / 'other', binding) as run:
            self.assertEqual(run.state['artifacts'], {})
        (path / 'sample.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'missing or changed'):
            RunStore(path, binding, resume=True)
    def test_unsupported_api_capabilities_and_unsafe_endpoint(self):
        profile = provider_profile(); profile['stages']['resolution']['seed'] = 1
        with self.assertRaisesRegex(ValueError, 'seed capability'):
            validate_provider(profile)
        profile = provider_profile(); profile['stages']['resolution']['enable_thinking'] = True
        with self.assertRaisesRegex(ValueError, 'thinking capability'):
            validate_provider(profile)
        for endpoint in ('http://example.com/v1', 'https://key:secret@example.com/v1', 'https://example.com/v1?api_key=secret'):
            with self.assertRaises(ValueError):
                safe_endpoint(endpoint)
    def test_compatible_http_fixture_and_secret_redaction(self):
        inv, prepared = self.prepared()
        with server_fixture() as (server, seen):
            profile = provider_profile(f'http://127.0.0.1:{server.server_port}/v1')
            with CompatibleBackend(profile, credential='test-secret') as backend:
                ledger = inference(self.case, prepared, RequestStore(self.root / 'http', backend, 100))
            self.assertEqual(ledger['status']['status'], 'complete')
            self.assertTrue(any(r.get('authorization') == 'Bearer test-secret' for r in seen))
        self.assertTrue(all('test-secret' not in p.read_text() for p in (self.root / 'http').glob('*.json')))
    def test_local_runtime_integrity_rejects_unknown_binary(self):
        runtime = self.root / 'runtime'; runtime.mkdir()
        for name in ('server.exe', 'model.gguf', 'template.jinja'):
            (runtime / name).write_text(name)
        profile = provider_profile(); profile['backend'] = 'llama-local'
        profile['model_sha256'] = file_hash(runtime / 'model.gguf')
        profile['chat_template_sha256'] = file_hash(runtime / 'template.jinja')
        manifest = self.root / 'runtime.json'
        write_json(manifest, {'schema': 'pkoc-runtime-v1', 'files': [{'file': 'server.exe', 'sha256': file_hash(runtime / 'server.exe')}]})
        assets = {'model': runtime / 'model.gguf', 'server': runtime / 'server.exe', 'chat_template': runtime / 'template.jinja', 'runtime_manifest': manifest}
        verified = runtime_receipt(profile, assets)
        self.assertEqual(verified['model_sha256'], profile['model_sha256'])
        (runtime / 'unknown.dll').write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'Unlisted executable'):
            runtime_receipt(profile, assets)
    def test_owned_local_launch_controls_and_http_fixture(self):
        runtime = self.root / 'runtime'; runtime.mkdir()
        for name in ('server.exe', 'model.gguf', 'template.jinja'):
            (runtime / name).write_text(name)
        profile = provider_profile(); profile['backend'] = 'llama-local'
        profile['capabilities']['tokenization'] = 'llama'
        profile['model_sha256'] = file_hash(runtime / 'model.gguf')
        profile['chat_template_sha256'] = file_hash(runtime / 'template.jinja')
        manifest = self.root / 'runtime.json'
        write_json(manifest, {'schema': 'pkoc-runtime-v1', 'files': [{'file': 'server.exe', 'sha256': file_hash(runtime / 'server.exe')}]})
        assets = {'model': runtime / 'model.gguf', 'server': runtime / 'server.exe', 'chat_template': runtime / 'template.jinja', 'runtime_manifest': manifest}
        verified = runtime_receipt(profile, assets)
        launches, managers = [], []
        class Process:
            pid = 12345
            returncode = None
            def poll(self): return self.returncode
            def terminate(self): self.returncode = 0
            def wait(self, timeout): return self.returncode
            def kill(self): self.returncode = -9
        def launch(args, **kwargs):
            launches.append((args, kwargs))
            manager = server_fixture(int(args[args.index('--port') + 1])); managers.append(manager); manager.__enter__()
            return Process()
        try:
            with patch('case_pipeline.providers.subprocess.Popen', side_effect=launch):
                with LocalBackend(profile, assets, self.root / 'owned', verified) as backend:
                    self.assertEqual(backend.receipt['owned_pid'], 12345)
                    inv, prepared = self.prepared()
                    ledger = inference(self.case, prepared, RequestStore(self.root / 'local-requests', backend, 100))
                self.assertEqual(ledger['status']['status'], 'complete')
                self.assertEqual(backend.process.returncode, 0)
            key = launches[0][1]['env']['LLAMA_API_KEY']
            self.assertGreater(len(key), 32)
            self.assertNotIn(key, json.dumps(backend.receipt))
            self.assertNotIn(key, str(launches[0][0]))
            self.assertIn('--no-webui', launches[0][0])
            self.assertIn('--no-cors-credentials', launches[0][0])
            self.assertIn('--jinja', launches[0][0])
            self.assertEqual(launches[0][0][launches[0][0].index('--host') + 1], '127.0.0.1')
            self.assertEqual(launches[0][1]['cwd'], runtime)
        finally:
            for manager in managers:
                manager.__exit__(None, None, None)
    def test_cli_default_preflight_does_not_create_run_or_call_api(self):
        case = self.root / 'case.json'; provider = self.root / 'provider.json'; output = self.root / 'dry'
        write_json(case, self.case); write_json(provider, provider_profile())
        args = parser().parse_args(['run', '--case', str(case), '--provider', str(provider), '--sources', str(self.sources), '--output', str(output)])
        result = execute(args)
        self.assertEqual(result['status'], 'preflight_only')
        self.assertFalse(output.exists())
    def test_full_cli_fixture_export_validation_and_cached_resume(self):
        case = self.root / 'case.json'; provider = self.root / 'provider.json'; output = self.root / 'cli-run'
        write_json(case, self.case)
        with server_fixture() as (server, seen):
            write_json(provider, provider_profile(f'http://127.0.0.1:{server.server_port}/v1'))
            argv = ['run', '--case', str(case), '--provider', str(provider), '--sources', str(self.sources),
                    '--output', str(output), '--execute', '--max-requests', '50']
            with patch.dict(os.environ, {'PKOC_TEST_KEY': 'test-secret'}):
                result = execute(parser().parse_args(argv))
                self.assertEqual(result['status'], 'complete')
                self.assertEqual(validate_run(output)['status'], 'passed')
                calls = len(seen)
                resumed = execute(parser().parse_args(argv + ['--resume']))
                self.assertEqual(resumed['status'], 'complete')
                self.assertEqual(len(seen), calls)
        exports = list((output / 'exports').glob('*/bundle.json'))
        self.assertEqual(len(exports), 1)
        bundle = read_json(exports[0])
        self.assertEqual(bundle['dataset']['kind'], 'model-only')
        graphml = list((output / 'exports').rglob('*.graphml'))
        self.assertEqual(len(graphml), 3)
        self.assertTrue(all('undirected' in p.read_text() for p in graphml))

    def test_duplicate_predictions_deduplicate_with_isolates(self):
        self.file.write_text('S/2000/13\n1. Governor Orin Kelm spoke.\n2. Lina Daro left.')
        inv, prepared = self.prepared()
        def duplicate(body):
            reply = fixture_reply(body)
            value = json.loads(reply['choices'][0]['message']['content'])
            if 'segments' in value and value['segments'][0]['occurrences']:
                value['segments'][0]['occurrences'].append(copy.deepcopy(value['segments'][0]['occurrences'][0]))
                reply['choices'][0]['message']['content'] = json.dumps(value)
            return reply
        ledger = inference(self.case, prepared, RequestStore(self.root / 'duplicates', FakeBackend(responder=duplicate), 100))
        self.assertEqual(len(ledger['occurrences']), 3)
        bundle = make_bundle(self.case, inv, prepared, ledger, 'b' * 64)
        self.assertEqual(len(bundle['occurrences']), 2)
        sentence = next(n for n in bundle['networks'] if n['scale'] == 'sentence')
        self.assertEqual(sentence['summary']['isolates'], 2)
        report = next(n for n in bundle['networks'] if n['scale'] == 'report')
        self.assertEqual(report['edges'][0]['weight'], 1)

    def test_schema_rejects_duplicate_or_unexpected_fields(self):
        schema = read_json(ROOT / 'protocol/case_pipeline/resolution.schema.json')
        with self.assertRaises(ValueError):
            validate_schema({'request_id': 'x', 'relations': [], 'confidence': 1}, schema)
        path = self.root / 'bad.json'; path.write_text('{"x":1,"x":2}')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            read_json(path)


if __name__ == '__main__':
    unittest.main()
