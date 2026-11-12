"""Executed source-only stage functions for inspection; not a full inference runner."""
import json, re, unicodedata
from difflib import SequenceMatcher

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def identifier(stage, packet):
    return 'N' + __import__('hashlib').sha256(canonical([stage, packet]).encode()).hexdigest()[:24]

def normalized(value):
    value = unicodedata.normalize('NFC', value).casefold()
    return ' '.join(value.translate(str.maketrans({'’': "'", '‘': "'", '‐': '-', '‑': '-', '–': '-'})).split())

def long_form(value):
    words = re.findall('[^\\W\\d_]+', value, flags=re.UNICODE)
    return len([w for w in words if len(w) > 1]) >= 2 and (not value.replace('.', '').isupper())

def order(occ, sources):
    p = sources[occ['paragraph_id']]
    return (p['publication_date'], p['report_id'], p['paragraph_id'], occ['start'], occ['end'])

def retrieve(surface, people):
    """All equality collisions, maximum five non-equality people, never merge."""
    target = normalized(surface)
    tokens = target.split()
    rows = []
    for pid, person in people.items():
        eligible = []
        for form in person['names']:
            norm = normalized(form)
            parts = norm.split()
            equal = norm == target
            sim = SequenceMatcher(None, target, norm).ratio()
            containment = bool(tokens and parts) and (set(tokens) <= set(parts) or set(parts) <= set(tokens))
            surname = bool(tokens and parts) and tokens[-1] == parts[-1] and (len(tokens[-1]) >= 3)
            if equal or sim >= 0.65 or containment or surname:
                eligible.append({'candidate_id': pid, 'matched_form': form, 'normalized_equal': equal, 'similarity': sim, 'token_containment': containment, 'surname_match': surname})
        if eligible:
            eligible.sort(key=lambda r: (not r['normalized_equal'], -r['similarity'], r['matched_form']))
            rows.append(eligible[0])
    rows.sort(key=lambda r: (not r['normalized_equal'], -r['similarity'], r['candidate_id']))
    return [r for r in rows if r['normalized_equal']] + [r for r in rows if not r['normalized_equal']][:5]

def disposition(surface, relations):
    """Uncertainty never becomes a forced new identity or a transitive merge."""
    same = [r['candidate_id'] for r in relations if r['decision'] == 'SAME' and (not r.get('evidence_conflict'))]
    if any((r.get('evidence_conflict') for r in relations)) or len(same) > 1:
        return {'status': 'unresolved', 'person_id': None, 'reason': 'conflicting_or_multiple_supported_links'}
    if len(same) == 1:
        return {'status': 'linked', 'person_id': same[0], 'reason': 'one_positive_contextual_link'}
    if long_form(surface) and all((r['decision'] == 'DIFFERENT' for r in relations)):
        return {'status': 'new_name_anchor', 'person_id': None, 'reason': 'no_retrieved_candidates' if not relations else 'all_retrieved_candidates_explicitly_different'}
    return {'status': 'unresolved', 'person_id': None, 'reason': 'short_form_or_insufficient_relationship_evidence'}

def evidence(p):
    return {'evidence_id': p['paragraph_id'], 'source_id': p['paragraph_id'], 'report_id': p['report_id'], 'text': p['text'], 'report_date': p['publication_date'], 'sha256': p['text_sha256']}

def segment(p):
    return {'segment_id': p['paragraph_id'], 'source_id': p['paragraph_id'], 'paragraph_id': p['paragraph_id'], 'report_id': p['report_id'], 'report_date': p['publication_date'], 'source_sha256': p['text_sha256'], 'coordinate_space': 'paragraph-local Unicode codepoints in the supplied canonical cleaned text; half-open start/end', 'text': p['text']}

def batches(rows, count=4, chars=6500):
    batch = []
    size = 0
    for row in rows:
        if batch and (row['report_id'] != batch[0]['report_id'] or len(batch) >= count or size + len(row['text']) > chars):
            yield batch
            batch = []
            size = 0
        batch.append(row)
        size += len(row['text'])
    if batch:
        yield batch

def broad_roles(assignment, claim):
    if assignment['status'] != 'SUPPORTED':
        return {'Unknown'}
    roles = set()
    un = bool(re.search('\\b(?:United Nations|UNMIL|UN)\\b', claim.get('affiliation_literal') or '', flags=re.I))
    for code in assignment['role_codes']:
        if code in {'GOV', 'MIL', 'COP', 'SPY'}:
            roles.add('Government')
        elif code == 'LEG':
            roles.add('Parliament')
        elif code in {'REB', 'INS', 'SEP'}:
            roles.add('Rebel')
        elif code == 'IGO' and un:
            roles.add('United Nations')
        elif code == 'UAF':
            roles.add('Unknown')
        else:
            roles.add('Others')
    return roles or {'Unknown'}
