"""Adaptive, evidence-bound model-only annotations; never a human-reviewed branch."""
from __future__ import annotations
import hashlib
from collections import defaultdict
from pathlib import Path
from inference_components import batches, disposition, evidence, identifier, retrieve, segment
from .common import PROTOCOL, ROOT, read_json
from .providers import BudgetExhausted


def ground(text, occurrence):
    """Unique exact match with immediately adjacent literal anchors; Python codepoints."""
    surface = occurrence['text']
    if not surface:
        return None, None, 'empty_surface'
    positions, cursor = [], 0
    while True:
        start = text.find(surface, cursor)
        if start < 0:
            break
        end = start + len(surface)
        left, right = occurrence.get('left_context'), occurrence.get('right_context')
        if (left is None or text[:start].endswith(left)) and (right is None or text[end:].startswith(right)):
            positions.append((start, end))
        cursor = start + 1
    if len(positions) == 1:
        return *positions[0], 'exact'
    return None, None, 'ambiguous' if positions else 'unmatched'


def check_ids(value, request_id, field, expected, item_key):
    if value['request_id'] != request_id:
        raise ValueError('Response request_id mismatch')
    actual = [row[item_key] for row in value[field]]
    if actual != expected:
        raise ValueError('Missing, duplicate, reordered or unknown response IDs')


def validate_evidence(ids, allowed, *, required=False):
    if len(ids) != len(set(ids)) or set(ids) - set(allowed) or (required and not ids):
        raise ValueError('Unknown, duplicate or missing evidence IDs')



def validate_literal(value, kind, case, paragraphs):
    """Fail prose-sized/full-paragraph predictions; never truncate source fields."""
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Source-derived literal must be a nonempty string or null')
    policy = case.get('literal_policy', {})
    limit = policy.get('max_name_codepoints', 160) if kind == 'name' else policy.get('max_attribute_codepoints', 400)
    if len(value) > limit:
        raise ValueError('Source-derived literal exceeds configured codepoint limit')
    normalized = ' '.join(value.split())
    if any(' '.join(p['text'].split()) in normalized for p in paragraphs if p['text'].strip()):
        raise ValueError('Source-derived literal contains a complete source paragraph')


def guard_publication_literals(bundle, case, prepared):
    for occurrence in bundle['occurrences']:
        validate_literal(occurrence['surface'], 'name', case, prepared['paragraphs'])
    for actor in bundle['nodes']:
        for name in [actor['name'], *actor.get('aliases', [])]:
            validate_literal(name, 'name', case, prepared['paragraphs'])
    for claim in bundle['claims']:
        for key in ('role_literal', 'office_literal', 'affiliation_literal'):
            validate_literal(claim.get(key), 'attribute', case, prepared['paragraphs'])


def inference(case, prepared, requests):
    paragraphs = prepared['paragraphs']
    sources = {p['paragraph_id']: p for p in paragraphs}
    by_sentence = defaultdict(list)
    for s in prepared['sentences']:
        by_sentence[s['paragraph_id']].append(s)
    schemas = {s: read_json(PROTOCOL / (s + '.schema.json')) for s in ('extraction', 'resolution', 'offices', 'cameo')}
    prompts = {s: (PROTOCOL / (s + '.txt')).read_text(encoding='utf-8-sig').replace('{{mission}}', case['mission']['name']) for s in schemas}
    codebook = read_json(ROOT / 'protocol' / 'codebook.json')
    occurrences, people, claims, attributes, decisions = [], {}, [], [], []
    coverage = {p['paragraph_id']: {'paragraph_id': p['paragraph_id'], 'status': 'not_processed', 'occurrences': 0} for p in paragraphs}
    state = {'status': 'complete', 'stage': 'extraction', 'budget_exhausted': False}

    def ask(stage, packet, validator):
        packet = dict(packet)
        packet['request_id'] = identifier('pkoc-v1-' + stage, packet)
        def checked(value):
            if value['request_id'] != packet['request_id']:
                raise ValueError('Response request_id mismatch')
            validator(value, packet)
        return requests.request(stage, packet, prompts[stage], schemas[stage], checked)

    try:
        for batch in batches(paragraphs, count=4, chars=6500):
            def check_extract(value, packet):
                check_ids(value, packet['request_id'], 'segments', [p['paragraph_id'] for p in batch], 'segment_id')
                for item in value['segments']:
                    for occurrence in item['occurrences']:
                        validate_literal(occurrence['text'], 'name', case, paragraphs)
                    if item['status'] == 'complete' and item['missing_context']:
                        raise ValueError('Complete extraction cannot claim missing context')
                    if item['status'] == 'insufficient_context' and not item['missing_context']:
                        raise ValueError('Insufficient context must identify missing information')
            value = ask('extraction', {'mission': case['mission'], 'segments': [segment(p) for p in batch]}, check_extract)
            if value is None:
                for p in batch:
                    coverage[p['paragraph_id']]['status'] = 'failed_or_context_excluded'
                continue
            for item in value['segments']:
                pid = item['segment_id']
                coverage[pid] = {'paragraph_id': pid, 'status': 'processed_empty' if item['status'] == 'complete' and not item['occurrences'] else item['status'],
                                 'occurrences': len(item['occurrences']), 'missing_context': item['missing_context']}
                seen = set()
                for number, raw_occ in enumerate(item['occurrences'], 1):
                    start, end, status = ground(sources[pid]['text'], raw_occ)
                    key = (start, end, raw_occ['text'])
                    duplicate = status == 'exact' and key in seen
                    if status == 'exact':
                        seen.add(key)
                    containing = [s['sentence_id'] for s in by_sentence[pid] if start is not None and s['start'] <= start and end <= s['end']]
                    occurrences.append({'workflow': 'L', 'occurrence_id': f'{pid}:m{number:03d}',
                                        'actor_id': None, 'report_id': sources[pid]['report_id'],
                                        'report_date': sources[pid]['publication_date'], 'paragraph_id': pid,
                                        'sentence_id': containing[0] if len(containing) == 1 else None,
                                        'start': start, 'end': end, 'surface': raw_occ['text'],
                                        'grounding_status': status, 'duplicate_prediction': duplicate,
                                        'identity_status': 'not_processed', 'raw_anchor': raw_occ})
        state['stage'] = 'resolution'
        for occ in occurrences:
            if occ['grounding_status'] != 'exact':
                occ['identity_status'] = 'excluded_ungrounded'
                continue
            if occ['duplicate_prediction']:
                original = next(o for o in occurrences if o is not occ and not o['duplicate_prediction'] and
                                (o['paragraph_id'], o['start'], o['end']) == (occ['paragraph_id'], occ['start'], occ['end']))
                occ['actor_id'], occ['identity_status'] = original['actor_id'], 'duplicate_prediction'
                continue
            candidates = retrieve(occ['surface'], people)
            relations = []
            if candidates:
                ids = {occ['paragraph_id']}
                for candidate in candidates:
                    ids.update(o['paragraph_id'] for o in people[candidate['candidate_id']]['occurrences'])
                quoted = [evidence(sources[pid]) for pid in sorted(ids)]
                target = {k: occ[k] for k in ('occurrence_id', 'surface', 'paragraph_id', 'start', 'end')}
                packet = {'mission': case['mission'], 'target': target, 'candidates': [
                    {**c, 'names': people[c['candidate_id']]['names'],
                     'occurrences': [{k: o[k] for k in ('occurrence_id', 'surface', 'paragraph_id', 'start', 'end')} for o in people[c['candidate_id']]['occurrences']]}
                    for c in candidates], 'evidence': quoted}
                def check_resolution(value, request):
                    check_ids(value, request['request_id'], 'relations', [c['candidate_id'] for c in candidates], 'candidate_id')
                    for rel in value['relations']:
                        validate_evidence(rel['evidence_ids'], ids, required=rel['decision'] != 'INSUFFICIENT')
                        if rel['decision'] == 'SAME':
                            candidate_ids = {o['paragraph_id'] for o in people[rel['candidate_id']]['occurrences']}
                            if occ['paragraph_id'] not in rel['evidence_ids'] or not candidate_ids.intersection(rel['evidence_ids']):
                                raise ValueError('SAME must cite target and candidate evidence')
                result = ask('resolution', packet, check_resolution)
                if result is None:
                    occ['identity_status'] = 'failed_or_context_excluded'
                    continue
                relations = result['relations']
            decision = disposition(occ['surface'], relations)
            actor = decision['person_id']
            if decision['status'] == 'new_name_anchor':
                actor = 'P' + hashlib.sha256((case['case_id'] + ':' + occ['occurrence_id']).encode()).hexdigest()[:20]
                people[actor] = {'actor_id': actor, 'names': [], 'occurrences': []}
            occ['actor_id'], occ['identity_status'] = actor, decision['status']
            decisions.append({'occurrence_id': occ['occurrence_id'], 'decision': decision, 'relations': relations})
            if actor:
                person = people[actor]
                if occ['surface'] not in person['names']:
                    person['names'].append(occ['surface'])
                person['occurrences'].append(occ)
        state['stage'] = 'attributes'
        for actor, person in people.items():
            by_report = defaultdict(list)
            for occ in person['occurrences']:
                by_report[occ['report_id']].append(occ)
            for report_id, report_occ in sorted(by_report.items()):
                ids = {o['paragraph_id'] for o in report_occ}
                quoted = [evidence(sources[pid]) for pid in sorted(ids)]
                person_packet = {'person_id': actor, 'names': person['names'], 'occurrences': [
                    {k: o[k] for k in ('occurrence_id', 'surface', 'paragraph_id', 'start', 'end')} for o in report_occ]}
                packet = {'mission': case['mission'], 'person': person_packet, 'report_id': report_id, 'evidence': quoted}
                def check_offices(value, request):
                    if value['person_id'] != actor:
                        raise ValueError('Office person ID mismatch')
                    claim_ids = [c['claim_id'] for c in value['claims']]
                    if len(set(claim_ids)) != len(claim_ids):
                        raise ValueError('Duplicate office claim ID')
                    if value['status'] == 'SUPPORTED' and not value['claims']:
                        raise ValueError('Supported offices must contain a claim')
                    for claim in value['claims']:
                        validate_evidence(claim['evidence_ids'], ids, required=True)
                        for field in ('role_literal', 'office_literal', 'affiliation_literal'):
                            literal = claim[field]
                            validate_literal(literal, 'attribute', case, paragraphs)
                            if literal is not None and not any(literal in sources[e]['text'] for e in claim['evidence_ids']):
                                raise ValueError('Office/affiliation literal is not contiguous source text')
                offices = ask('offices', packet, check_offices)
                attribute = {'workflow': 'L', 'actor_id': actor, 'report_id': report_id,
                             'role_codes': [], 'specialty_codes': [], 'cameo_codes': [], 'primary_cameo_codes': [],
                             'applied_claim_keys': [], 'primary_applied_claim_keys': [],
                             'applicability_assumption': 'observation_in_this_report_only',
                             'source_evidence_issues': [], 'uncertainty': []}
                attributes.append(attribute)
                if offices is None:
                    attribute['uncertainty'].append('office_extraction_failed_or_context_excluded')
                    continue
                if offices['status'] != 'SUPPORTED':
                    attribute['uncertainty'].append('office_' + offices['status'].lower())
                if not offices['claims']:
                    continue
                claim_map = {c['claim_id']: c for c in offices['claims']}
                def check_codes(value, request):
                    if value['person_id'] != actor:
                        raise ValueError('CAMEO person ID mismatch')
                    check_ids(value, request['request_id'], 'assignments', list(claim_map), 'claim_id')
                    for assignment in value['assignments']:
                        original = claim_map[assignment['claim_id']]
                        for field in ('role_literal', 'office_literal', 'affiliation_literal'):
                            if assignment[field] != original[field]:
                                raise ValueError('CAMEO modified the literal source title')
                        validate_evidence(assignment['evidence_ids'], ids, required=assignment['status'] == 'SUPPORTED')
                        if assignment['status'] == 'SUPPORTED' and (not assignment['role_codes'] or not set(original['evidence_ids']) <= set(assignment['evidence_ids'])):
                            raise ValueError('Supported code needs role and original evidence')
                        if assignment['status'] != 'SUPPORTED' and (assignment['role_codes'] or assignment['specialty_codes']):
                            raise ValueError('Unsupported assignments must have empty codes')
                        for field in ('role_codes', 'specialty_codes'):
                            if len(assignment[field]) != len(set(assignment[field])):
                                raise ValueError('Duplicate code')
                assignments = ask('cameo', {**packet, 'claims': offices['claims'], 'codebook': codebook}, check_codes)
                coded = {a['claim_id']: a for a in assignments['assignments']} if assignments else {}
                if not assignments:
                    attribute['uncertainty'].append('cameo_failed_or_context_excluded')
                for local_id, claim in claim_map.items():
                    a = coded.get(local_id)
                    claim_key = identifier('claim', [actor, report_id, claim])
                    role = a['role_codes'] if a else []
                    specialty = a['specialty_codes'] if a else []
                    support = 'supported' if a and a['status'] == 'SUPPORTED' else 'unresolved'
                    row = {'workflow': 'L', 'actor_id': actor, 'claim_key': claim_key,
                           'role_literal': claim['role_literal'], 'office_literal': claim['office_literal'],
                           'affiliation_literal': claim['affiliation_literal'], 'capacity_status': claim['capacity_status'],
                           'role_codes': role, 'specialty_codes': specialty, 'cameo_codes': sorted(set(role + specialty)),
                           'assignment_status': a['status'] if a else 'FAILED', 'evidence_ids': claim['evidence_ids'],
                           'evidence_occurrence_ids': [o['occurrence_id'] for o in report_occ if o['paragraph_id'] in claim['evidence_ids']],
                           'evidence_report_ids': [report_id], 'source_report_id': report_id,
                           'report_years': sorted({int(sources[e]['publication_date'][:4]) for e in claim['evidence_ids'] if sources[e]['publication_date']}),
                           'assumption': 'observation_in_this_report_only', 'support_status': support, 'origin': 'model-only'}
                    claims.append(row)
                    attribute['applied_claim_keys'].append(claim_key)
                    if support == 'supported':
                        attribute['primary_applied_claim_keys'].append(claim_key)
                        attribute['role_codes'] += role
                        attribute['specialty_codes'] += specialty
                    else:
                        attribute['uncertainty'].append('claim_' + row['assignment_status'].lower())
                attribute['role_codes'] = sorted(set(attribute['role_codes']))
                attribute['specialty_codes'] = sorted(set(attribute['specialty_codes']))
                attribute['cameo_codes'] = sorted(set(attribute['role_codes'] + attribute['specialty_codes']))
                attribute['primary_cameo_codes'] = attribute['cameo_codes'][:]
        state['stage'] = 'finished'
    except BudgetExhausted:
        state.update(status='partial', budget_exhausted=True)
    except KeyboardInterrupt:
        state.update(status='interrupted', interrupted=True)
    failures = [e for e in requests.events if e['status'] in ('failed', 'excluded_context_limit')]
    if failures and state['status'] == 'complete':
        state['status'] = 'complete_with_failures'
    # A stopped resolution stage must not look like an all-empty corpus.
    state.update(attempts=requests.attempt_count, request_cap=requests.max_requests,
                 paragraphs_total=len(paragraphs), paragraphs_processed=sum(c['status'] not in ('not_processed', 'failed_or_context_excluded') for c in coverage.values()),
                 unresolved_occurrences=sum(o['actor_id'] is None for o in occurrences),
                 unique_actors=len(people), failures=len(failures))
    nodes = []
    for actor, person in people.items():
        codes = sorted({c for a in attributes if a['actor_id'] == actor for c in a['cameo_codes']})
        nodes.append({'workflow': 'L', 'actor_id': actor, 'name': person['names'][0], 'aliases': person['names'][1:],
                      'cameo_codes': codes, 'primary_cameo_codes': codes, 'identity_origin': 'model-only'})
    return {'schema': 'pkoc-model-ledger-v1', 'status': state, 'nodes': nodes, 'occurrences': occurrences,
            'claims': claims, 'attributes': attributes, 'coverage': list(coverage.values()),
            'identity_decisions': decisions, 'request_events': requests.events,
            'human_reviewed': False, 'workflow': 'L'}


def make_bundle(case, inv, prepared, ledger, binding_sha256):
    """Publication-oriented allowlist; no raw paragraphs, prompts, logs, or reasoning."""
    occurrence_fields = ('workflow', 'occurrence_id', 'actor_id', 'report_id', 'report_date', 'paragraph_id',
                         'sentence_id', 'start', 'end', 'surface', 'grounding_status', 'identity_status')
    from explorer_data import project_network, validate_bundle
    codebook = read_json(ROOT / 'protocol' / 'codebook.json')
    bundle = {'schema': 'pkoc-explorer-v1',
              'dataset': {'id': case['case_id'], 'title': case['title'], 'kind': 'model-only', 'rosters': ['L'],
                          'coordinate_policy': 'paragraph-local zero-based half-open Unicode codepoints'},
              'reports': [{k: r[k] for k in ('report_id', 'document_symbol', 'report_date', 'year', 'official_url')} for r in inv['reports']],
              'nodes': ledger['nodes'],
              'occurrences': [{**{k: o[k] for k in occurrence_fields}, 'grounding_status': 'grounded' if o['grounding_status'] == 'exact' else o['grounding_status']} for o in ledger['occurrences'] if not o['duplicate_prediction']],
              'attributes': ledger['attributes'], 'claims': ledger['claims'],
              'paragraphs': [{k: p[k] for k in ('paragraph_id', 'report_id', 'publication_date', 'text_sha256')} for p in prepared['paragraphs']],
              'sentences': prepared['sentences'], 'interventions': [], 'correspondence': [], 'reference_units': [],
              'networks': [], 'codebook': [{'code': c, 'label': c, 'definition': d} for c, d in sorted(codebook['definitions'].items())],
              'provenance': {'origin': 'scripted fictional demonstration, not LLM inference' if case.get('synthetic_fixture') else 'automated toolkit output',
                             'synthetic_fixture': case.get('synthetic_fixture', False), 'run_binding_sha256': binding_sha256,
                             'source_hashes': {r['document_symbol']: r['sha256'] for r in inv['reports']},
                             'inference_status': ledger['status'], 'coverage': [{k: c[k] for k in ('paragraph_id', 'status', 'occurrences')} for c in ledger['coverage']],
                             'human_reviewed': False, 'publication_rights_reviewed': False,
                             'rights_notice': 'Private preparation; separate rights review and instruction required before publication.',
                             'network_contract': 'Binary actor presence per unit; undirected weighted co-occurrence; isolates retained.',
                             'limitations': ['Model-only outputs; no A/R branch', 'Report observations do not establish continuous presence or tenure',
                                            'Fresh inference is not bitwise reproducible or equivalent across providers',
                                            'Historical PDF extraction is not reproduced from newly downloaded PDFs']}}
    guard_publication_literals(bundle, case, prepared)
    bundle['networks'] = [project_network(bundle, 'L', scale) for scale in ('sentence', 'paragraph', 'report')]
    validate_bundle(bundle)
    return bundle
