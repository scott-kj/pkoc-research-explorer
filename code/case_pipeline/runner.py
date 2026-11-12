"""CLI orchestration for independently owned, resumable case runs."""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
from .attempts import verify_registry
from .common import ROOT, RunStore, canonical, code_hashes, digest, file_hash, integer, read_json, utc
from .ingest import inventory, prepare, validate_case
from .inference import inference, make_bundle
from .providers import CompatibleBackend, LocalBackend, RequestStore, runtime_receipt, validate_provider


def validate_run(path):
    path = Path(path).resolve()
    state = read_json(path / 'run-state.json')
    if digest(state['binding']) != state['binding_sha256']:
        raise ValueError('Run binding changed')
    checked = 0
    for relative, expected in state['artifacts'].items():
        member = (path / relative).resolve()
        if path not in member.parents or not member.is_file() or file_hash(member) != expected:
            raise ValueError('Run artifact missing/modified: ' + relative)
        checked += 1
    requests_path = path / 'private' / 'requests'
    registry = state.get('request_registry')
    if registry is not None:
        verify_registry(requests_path, registry)
    elif any(requests_path.glob('*.start.json')) or any(requests_path.glob('*.finish.json')):
        raise ValueError('Native receipts have no durable run registry')
    for start in sorted(requests_path.glob('*.start.json')):
        request = read_json(start)
        if digest(request['request']) != request['request_sha256']:
            raise ValueError('Native request hash mismatch')
        finish = start.with_name(start.name.replace('.start.json', '.finish.json'))
        if finish.exists():
            response = read_json(finish)
            if response['start_sha256'] != file_hash(start) or digest(response['native_response']) != response['response_sha256']:
                raise ValueError('Native response hash mismatch')
            checked += 1
    if (path / 'bundle.json').exists():
        from explorer_data import project_network, validate_bundle
        bundle = read_json(path / 'bundle.json')
        validate_bundle(bundle)
        for network in bundle['networks']:
            if project_network(bundle, network['workflow'], network['scale']) != network:
                raise ValueError('Network does not match binary incidence projection')
    prepared_path = path / 'prepared.json'
    if prepared_path.exists():
        import hashlib
        prepared = read_json(prepared_path)
        sources = {p['paragraph_id']: p for p in prepared['paragraphs']}
        for p in sources.values():
            if hashlib.sha256(p['text'].encode()).hexdigest() != p['text_sha256'] or len(p['text']) != len(p['source_codepoint_spans']):
                raise ValueError('Canonical text/hash/source map mismatch')
        for s in prepared['sentences']:
            p = sources[s['paragraph_id']]
            if not 0 <= s['start'] < s['end'] <= len(p['text']):
                raise ValueError('Sentence boundary outside canonical paragraph')
        ledger_path = path / 'ledger.json'
        if ledger_path.exists():
            for o in read_json(ledger_path)['occurrences']:
                if o['grounding_status'] == 'exact':
                    p = sources[o['paragraph_id']]
                    if o['start'] is None or p['text'][o['start']:o['end']] != o['surface']:
                        raise ValueError('Occurrence is not exactly grounded')
    return {'schema': 'pkoc-validation-v1', 'validated_utc': utc(), 'checked_artifacts': checked,
            'run_binding_sha256': state['binding_sha256'], 'status': 'passed',
            'scope': 'Stored artifacts, native receipt hashes, canonical boundaries, exact grounding and network projection; not human factual review',
            'inference_status': state['stages'].get('infer', {})}


def parser():
    p = argparse.ArgumentParser(description='Reusable PKOC annotation-to-network toolkit; run outputs stay local')
    p.add_argument('command', choices=('inventory', 'prepare', 'infer', 'network', 'export', 'validate', 'status', 'run'))
    p.add_argument('--case', type=Path, help='Explicit case selection JSON')
    p.add_argument('--provider', type=Path, help='Provider capability/generation JSON')
    p.add_argument('--sources', type=Path, help='English PKOC archived extraction text directory')
    p.add_argument('--catalog', type=Path, help='Optional PKOC CSV catalog (duplicate headers interpreted positionally)')
    p.add_argument('--output', type=Path, help='New or empty run directory; runs/ is ignored')
    p.add_argument('--resume', action='store_true', help='Resume only an owned run with unchanged hashes and request cap')
    p.add_argument('--execute', action='store_true', help='Explicitly permit inference requests for infer/run')
    p.add_argument('--max-requests', type=int, default=100, help='Hard total inference-attempt cap, including failed/interrupted calls')
    p.add_argument('--model', type=Path, help='Local GGUF, never copied or committed')
    p.add_argument('--server', type=Path, help='Verified llama-server executable')
    p.add_argument('--chat-template', type=Path, help='Verified local Jinja template')
    p.add_argument('--runtime-manifest', type=Path, help='pkoc-runtime-v1 file/hash allowlist for installed runtime')
    return p



def status_summary(state, lock_present):
    """Describe saved stage scope without treating a lock as proof of liveness."""
    stages = state.get('stages', {})
    recorded = state.get('status', 'created')
    stage_status = {name: value.get('status') for name, value in stages.items()}
    full_stages = ('inventory', 'prepare', 'infer', 'network', 'export', 'validate')
    all_complete = all(stage_status.get(name) == 'complete' for name in full_stages)
    complete = False
    if lock_present:
        status, scope = 'active_or_interrupted', 'not_established_while_lock_present'
    elif recorded in ('failed', 'interrupted', 'partial', 'complete_with_failures'):
        status, scope = recorded, 'inference_' + recorded if recorded in ('partial', 'complete_with_failures') else 'failed_or_interrupted'
    elif stage_status.get('infer') in ('failed', 'interrupted', 'partial', 'complete_with_failures'):
        status = stage_status['infer']
        scope = 'inference_' + status
    elif all_complete:
        status, scope, complete = 'complete', 'full_run', True
    elif stage_status.get('infer') == 'complete':
        if stage_status.get('export') == 'complete':
            status, scope = 'exported', 'export_without_complete_run_validation'
        elif stage_status.get('network') == 'complete':
            status, scope = 'networks_complete', 'networks_without_export'
        else:
            status, scope = 'inference_complete', 'inference_only'
    elif state.get('request_registry', {}).get('total_reserved', 0):
        status, scope = 'incomplete', 'inference_attempts_without_final_receipt'
    elif stage_status.get('prepare') == 'complete':
        status, scope = 'prepared', 'preparation_only'
    elif stage_status.get('inventory') == 'complete':
        status, scope = 'inventoried', 'inventory_only'
    else:
        status, scope = 'created', 'no_completed_stages'
    result = {key: state[key] for key in ('schema', 'binding_sha256', 'created_utc', 'updated_utc', 'stages')}
    result.update(status=status, recorded_status=recorded, completion_scope=scope,
                  full_run_complete=complete, lock_present=lock_present, process_liveness='not_checked')
    return result


def execute(args):
    began = time.monotonic()
    integer(args.max_requests, 'max_requests')
    if args.command in ('status', 'validate'):
        if args.output is None:
            raise ValueError('--output is required')
        if args.command == 'validate':
            return validate_run(args.output)
        state = read_json(args.output / 'run-state.json')
        return status_summary(state, (args.output / '.run.lock').exists())
    if args.case is None or args.sources is None:
        raise ValueError('--case and --sources are required')
    case = validate_case(read_json(args.case))
    inv = inventory(case, args.sources, args.catalog)
    if args.command == 'inventory':
        return inv
    if args.provider is None:
        raise ValueError('--provider is required for a run; its settings are bound before preparation')
    profile = validate_provider(read_json(args.provider))
    assets = {'model': args.model, 'server': args.server, 'chat_template': args.chat_template,
              'runtime_manifest': args.runtime_manifest}
    runtime_manifest_hash = file_hash(args.runtime_manifest) if args.runtime_manifest else None
    binding = {'case': case, 'provider': profile, 'inventory': inv,
               'max_requests': args.max_requests, 'runtime_manifest_sha256': runtime_manifest_hash,
               'code_hashes': code_hashes()}
    if args.command in ('infer', 'run') and not args.execute:
        verified = runtime_receipt(profile, assets)
        return {'status': 'preflight_only', 'execution_permitted': False, 'binding_sha256': digest(binding),
                'documents': len(inv['reports']), 'request_cap': args.max_requests,
                'runtime': verified, 'note': 'No model process or inference request started; add --execute explicitly.'}
    if args.output is None:
        raise ValueError('--output is required')
    output = args.output.resolve()
    if ROOT in output.parents and output.relative_to(ROOT).parts[0] != 'runs':
        raise ValueError('Run directories inside this checkout must be under ignored runs/')
    # The output must not overlap the read-only source archive in either direction.
    source_root = args.sources.resolve()
    if output == source_root or output in source_root.parents or source_root in output.parents:
        raise ValueError('Output must be separate from the source archive')
    with RunStore(args.output, binding, resume=args.resume) as store:
        if 'inventory.json' not in store.state['artifacts']:
            store.write('inventory.json', inv)
            store.stage('inventory', 'complete', reports=len(inv['reports']))
        if 'prepared.json' not in store.state['artifacts']:
            prepared = prepare(case, args.sources, inv)
            store.write('prepared.json', prepared)
            store.stage('prepare', 'complete', paragraphs=len(prepared['paragraphs']), sentences=len(prepared['sentences']))
        else:
            prepared = read_json(output / 'prepared.json')
        if args.command == 'prepare':
            return {'status': 'prepared', 'paragraphs': len(prepared['paragraphs']), 'binding_sha256': store.binding_hash}
        ledger = read_json(output / 'ledger.json') if (output / 'ledger.json').exists() else None
        if args.command in ('infer', 'run') and (ledger is None or ledger['status']['status'] in ('partial', 'interrupted')):
            verified = runtime_receipt(profile, assets)
            store.write('private/runtime-verification.json', verified)
            backend = LocalBackend(profile, assets, output / 'private' / 'server', verified) if profile['backend'] == 'llama-local' else CompatibleBackend(profile)
            requests = RequestStore(output / 'private' / 'requests', backend, args.max_requests, owner=store)
            try:
                with backend:
                    store.write('private/provider-receipt.json', backend.receipt)
                    ledger = inference(case, prepared, requests)
                    store.write('ledger.json', ledger)
                    store.stage('infer', ledger['status']['status'], **{k: v for k, v in ledger['status'].items() if k != 'status'})
            finally:
                store.write('private/provider-receipt.json', backend.receipt)
            if args.command == 'infer':
                return ledger['status']
        if ledger is None:
            raise ValueError('Run inference first; no model ledger exists')
        if inventory(case, args.sources, args.catalog) != inv or read_json(args.case) != case or read_json(args.provider) != profile or code_hashes() != binding['code_hashes']:
            raise ValueError('Inputs, profiles or code changed during run; export rejected')
        bundle = make_bundle(case, inv, prepared, ledger, store.binding_hash)
        store.write('bundle.json', bundle)
        store.stage('network', 'complete', networks=[{'scale': n['scale'], **n['summary']} for n in bundle['networks']],
                    inference_status=ledger['status']['status'])
        if args.command in ('export', 'run'):
            from explorer_data import write_bundle
            destination = output / 'exports' / digest(bundle)[:16]
            if destination.exists() and any(destination.iterdir()):
                if read_json(destination / 'bundle.json') != bundle:
                    raise ValueError('Existing export destination differs')
            else:
                write_bundle(bundle, destination, web_root=ROOT / 'web' if (ROOT / 'web' / 'index.html').exists() else None)
            for file in destination.rglob('*'):
                if file.is_file():
                    store.state['artifacts'][file.relative_to(output).as_posix()] = file_hash(file)
            store.stage('export', 'complete', directory=destination.relative_to(output).as_posix(),
                        publication_authorized=False, source_prose_included=False)
        report = validate_run(output)
        report['runtime_seconds'] = time.monotonic() - began
        report['inference_status'] = ledger['status']
        store.write('validation.json', report)
        store.stage('validate', 'complete', scope=report['scope'])
        store.state['status'] = 'complete' if ledger['status']['status'] == 'complete' else ledger['status']['status']
        store.save()
        return {'status': store.state['status'], 'inference': ledger['status'], 'validation': report,
                'binding_sha256': store.binding_hash}


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('status') in ('partial', 'interrupted', 'complete_with_failures') else 0
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(json.dumps({'status': 'error', 'type': type(exc).__name__, 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
