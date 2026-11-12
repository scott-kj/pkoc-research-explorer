"""Regressions for immutable request budgets and source-free model exports."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from case_pipeline.attempts import verify_registry
from case_pipeline.common import RunStore, file_hash, read_json, write_json
from case_pipeline.ingest import inventory, prepare
from case_pipeline.inference import inference, make_bundle, validate_literal
from case_pipeline.providers import CompatibleBackend, RequestStore
from test_case_pipeline import FakeBackend, case_profile, fixture_reply, provider_profile


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.sources = self.root / 'sources'; self.sources.mkdir()
        self.file = self.sources / 'S_2000_13_E.pdf.txt'
        self.file.write_text('S/2000/13\n11 January 2000\n1. Governor Orin Kelm met Lina Daro. Orin Kelm left.\n2. Nobody was named.', encoding='utf8')
        self.case = case_profile()
        self.inv = inventory(self.case, self.sources)
        self.prepared = prepare(self.case, self.sources, self.inv)
    def tearDown(self):
        self.temp.cleanup()
    def test_deleted_started_finished_and_all_receipts_rejected(self):
        for kind in ('start', 'finish', 'all'):
            with self.subTest(kind=kind):
                output = self.root / kind
                with RunStore(output, {'fixture': kind}) as owner:
                    ledger = inference(self.case, self.prepared, RequestStore(output / 'private/requests', FakeBackend(), 20, owner=owner))
                    consumed = owner.state['request_registry']['total_reserved']
                    self.assertGreater(consumed, 0)
                receipts = output / 'private/requests'
                chosen = list(receipts.glob('*.json')) if kind == 'all' else [next(receipts.glob('*.' + kind + '.json'))]
                for path in chosen:
                    path.unlink()
                with self.assertRaisesRegex(ValueError, 'Missing indexed'):
                    RunStore(output, {'fixture': kind}, resume=True)
                self.assertEqual(read_json(output / 'run-state.json')['request_registry']['total_reserved'], consumed)
    def test_orphan_receipt_and_tampered_finish_rejected(self):
        path = self.root / 'requests'
        inference(self.case, self.prepared, RequestStore(path, FakeBackend(), 20))
        orphan = path / 'not-reserved-01.finish.json'; write_json(orphan, {})
        with self.assertRaisesRegex(ValueError, 'Orphan'):
            RequestStore(path, FakeBackend(), 20)
        orphan.unlink()
        finish = next(path.glob('*.finish.json'))
        value = read_json(finish); value['outcome'] = 'forged'; write_json(finish, value)
        with self.assertRaisesRegex(ValueError, 'finish receipt hash'):
            RequestStore(path, FakeBackend(), 20)
    def test_reservation_before_start_crash_keeps_consumed_budget(self):
        output = self.root / 'reserved'
        with RunStore(output, {'fixture': 1}) as owner:
            requests = RequestStore(output / 'private/requests', FakeBackend(), 1, owner=owner)
            with patch('case_pipeline.providers.write_json', side_effect=KeyboardInterrupt):
                ledger = inference(self.case, self.prepared, requests)
            self.assertEqual(ledger['status']['status'], 'interrupted')
            self.assertEqual(owner.state['request_registry']['attempts'][0]['phase'], 'reserved')
            self.assertEqual(requests.attempt_count, 1)
            self.assertEqual(list((output / 'private/requests').glob('*.start.json')), [])
        with RunStore(output, {'fixture': 1}, resume=True) as owner:
            backend = FakeBackend()
            ledger = inference(self.case, self.prepared, RequestStore(output / 'private/requests', backend, 1, owner=owner))
            self.assertEqual(ledger['status']['status'], 'partial')
            self.assertEqual(backend.calls, [])
    def test_finish_before_registry_crash_is_recovered_without_new_call(self):
        output = self.root / 'finish-crash'
        with RunStore(output, {'fixture': 2}) as owner:
            requests = RequestStore(output / 'private/requests', FakeBackend(), 1, owner=owner)
            with patch.object(requests.registry, 'finished', side_effect=KeyboardInterrupt):
                ledger = inference(self.case, self.prepared, requests)
            self.assertEqual(ledger['status']['status'], 'interrupted')
            self.assertEqual(owner.state['request_registry']['attempts'][0]['phase'], 'started')
            self.assertEqual(len(list((output / 'private/requests').glob('*.finish.json'))), 1)
        with RunStore(output, {'fixture': 2}, resume=True) as owner:
            backend = FakeBackend()
            requests = RequestStore(output / 'private/requests', backend, 1, owner=owner)
            self.assertEqual(requests.registry.data['attempts'][0]['phase'], 'finished')
            ledger = inference(self.case, self.prepared, requests)
            self.assertEqual(backend.calls, [])
            self.assertEqual(ledger['status']['status'], 'partial')
    def test_counter_mismatch_and_registry_deleted_with_receipts_rejected(self):
        path = self.root / 'counter'
        request_store = RequestStore(path, FakeBackend(), 20)
        inference(self.case, self.prepared, request_store)
        changed = copy.deepcopy(request_store.registry.data); changed['total_reserved'] = 0
        with self.assertRaisesRegex(ValueError, 'counter/registry'):
            verify_registry(path, changed)
        request_store.registry.checkpoint.unlink()
        with self.assertRaisesRegex(ValueError, 'no durable registry'):
            RequestStore(path, FakeBackend(), 20)
    def test_malformed_native_envelopes_have_two_failed_finish_receipts(self):
        for index, native in enumerate((None, [], 'bad', 7, float('nan'), {'choices': [None]}, {'choices': [{'finish_reason': 'stop', 'message': None}]})):
            with self.subTest(native=native):
                path = self.root / f'malformed-{index}'
                requests = RequestStore(path, FakeBackend(responder=lambda body: native), 2)
                ledger = inference(self.case, self.prepared, requests)
                self.assertEqual(ledger['status']['status'], 'complete_with_failures')
                self.assertEqual(requests.attempt_count, 2)
                self.assertEqual(len(list(path.glob('*.finish.json'))), 2)
                self.assertTrue(all(read_json(p)['outcome'] == 'failed' for p in path.glob('*.finish.json')))
    def test_invalid_native_json_retained_as_redacted_bounded_failure(self):
        for index, payload in enumerate((b'{"choices": [], "choices": []}', b'{"x": NaN}', b'bad JSON test-secret')):
            class Response:
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def read(self, maximum): return payload
            backend = CompatibleBackend(provider_profile(), credential='test-secret')
            path = self.root / f'invalid-json-{index}'
            with patch.object(backend.opener, 'open', return_value=Response()):
                ledger = inference(self.case, self.prepared, RequestStore(path, backend, 2))
            self.assertEqual(ledger['status']['status'], 'complete_with_failures')
            records = [read_json(p) for p in path.glob('*.finish.json')]
            self.assertEqual(len(records), 2)
            self.assertTrue(all('raw_body' in row['error']['message'] for row in records))
            self.assertNotIn('test-secret', json.dumps(records))

    def test_full_paragraph_office_prediction_is_failed_not_exported(self):
        source_text = self.prepared['paragraphs'][0]['text']
        def paragraph_office(body):
            reply = fixture_reply(body)
            value = json.loads(reply['choices'][0]['message']['content'])
            if 'claims' in value and value['claims']:
                value['claims'][0]['role_literal'] = source_text
                value['claims'][0]['office_literal'] = source_text
                reply['choices'][0]['message']['content'] = json.dumps(value)
            return reply
        ledger = inference(self.case, self.prepared, RequestStore(self.root / 'office', FakeBackend(responder=paragraph_office), 20))
        self.assertEqual(ledger['status']['status'], 'complete_with_failures')
        self.assertEqual(ledger['claims'], [])
        bundle = make_bundle(self.case, self.inv, self.prepared, ledger, 'a' * 64)
        self.assertNotIn(source_text, json.dumps(bundle))
        self.assertTrue(any('office_extraction_failed' in u for a in bundle['attributes'] for u in a['uncertainty']))
    def test_full_paragraph_name_and_length_overflow_are_failed(self):
        source_text = self.prepared['paragraphs'][0]['text']
        def paragraph_name(body):
            reply = fixture_reply(body); value = json.loads(reply['choices'][0]['message']['content'])
            if 'segments' in value:
                value['segments'][0]['occurrences'] = [{'text': source_text, 'left_context': None, 'right_context': None}]
                reply['choices'][0]['message']['content'] = json.dumps(value)
            return reply
        ledger = inference(self.case, self.prepared, RequestStore(self.root / 'name', FakeBackend(responder=paragraph_name), 20))
        self.assertEqual(ledger['status']['status'], 'complete_with_failures')
        self.assertEqual(ledger['occurrences'], [])
        with self.assertRaisesRegex(ValueError, 'codepoint limit'):
            validate_literal('x' * 161, 'name', self.case, self.prepared['paragraphs'])
        customized = copy.deepcopy(self.case); customized['literal_policy'] = {'max_name_codepoints': 200}
        validate_literal('x' * 161, 'name', customized, self.prepared['paragraphs'])
        validate_literal('😀' * 160, 'name', self.case, self.prepared['paragraphs'])
    def test_final_export_guards_surfaces_names_aliases_and_all_claim_literals(self):
        ledger = inference(self.case, self.prepared, RequestStore(self.root / 'final', FakeBackend(), 20))
        text = self.prepared['paragraphs'][0]['text']
        for field in ('surface', 'name', 'alias', 'role_literal', 'office_literal', 'affiliation_literal'):
            with self.subTest(field=field):
                altered = copy.deepcopy(ledger)
                if field == 'surface': altered['occurrences'][0]['surface'] = text
                elif field == 'name': altered['nodes'][0]['name'] = text
                elif field == 'alias': altered['nodes'][0]['aliases'].append(text)
                else: altered['claims'][0][field] = text
                with self.assertRaisesRegex(ValueError, 'complete source paragraph'):
                    make_bundle(self.case, self.inv, self.prepared, altered, 'a' * 64)
    def test_inventory_and_prepare_hash_the_captured_bytes(self):
        original = self.file.read_bytes()
        replacement = original.replace(b'Governor', b'Minister')
        original_read = Path.read_bytes
        def changed_capture(path):
            return replacement if path == self.file else original_read(path)
        with patch.object(Path, 'read_bytes', changed_capture):
            with self.assertRaisesRegex(ValueError, 'during inventory capture'):
                inventory(self.case, self.sources)
            with self.assertRaisesRegex(ValueError, 'changed after inventory'):
                prepare(self.case, self.sources, self.inv)
        self.assertEqual(self.file.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
