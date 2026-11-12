"""Explicit document selection, header checks, and source-mapped text preparation."""
from __future__ import annotations
import calendar
import csv
import hashlib
import re
from datetime import date
from pathlib import Path
import corpus
from segmentation import sentence_spans
from .common import digest, file_hash, integer

SYMBOL = re.compile(r'\bS/(\d{4})/(\d+)(?:/(Add|Corr)\.(\d+))?\b', re.I)
FILE = re.compile(r'^S_(\d{4})_(\d+)(?:_(Add|Corr)[._]?(\d+))?_E(?:\.pdf)?\.txt$', re.I)
MONTHS = {name.lower(): number for number, name in enumerate(calendar.month_name) if name}
DATE = re.compile(r'(?m)^[ \t]*(\d{1,2})[ \t]+(' + '|'.join(MONTHS) + r')\s+(\d{4})(?!\d)', re.I)
MONTH_DATE = re.compile(r'(?m)^[ \t]*(' + '|'.join(MONTHS) + r')\s+(\d{4})(?!\d)', re.I)


def symbol_from_match(match):
    value = f'S/{match[1]}/{int(match[2])}'
    return value + (f'/{match[3].title()}.{int(match[4])}' if match[3] else '')


def normalize_symbol(value):
    match = SYMBOL.fullmatch(value.strip())
    if not match:
        raise ValueError('Unsupported PKOC document symbol: ' + value)
    return symbol_from_match(match)


def parse_partial_date(value):
    if value is None or value == '':
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}(?:-\d{2}(?:-\d{2})?)?', value):
        raise ValueError('Dates must be ISO year, year-month, complete date, or null')
    bits = [int(p) for p in value.split('-')]
    date(bits[0], bits[1] if len(bits) > 1 else 1, bits[2] if len(bits) > 2 else 1)
    return value


def read_catalog(path):
    """Keep duplicate header positions; filename column is never used as a path."""
    if path is None:
        return [], []
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.reader(handle)
        headers = next(reader)
        stripped = [h.strip() for h in headers]
        symbol_columns = [i for i, h in enumerate(stripped) if h == 'Document_ID']
        if not symbol_columns:
            raise ValueError('Catalog has no Document_ID column')
        rows, warnings = [], []
        if len(symbol_columns) > 1:
            warnings.append('Duplicate Document_ID headers interpreted positionally; symbol and slug are distinct')
        for line, values in enumerate(reader, 2):
            if len(values) != len(headers):
                raise ValueError(f'Catalog row {line} has inconsistent column count')
            symbols = [normalize_symbol(values[i]) for i in symbol_columns if SYMBOL.fullmatch(values[i].strip())]
            if len(set(symbols)) != 1:
                raise ValueError(f'Catalog row {line} has missing or conflicting document symbols')
            record = {'document_symbol': symbols[0], 'catalog_line': line}
            for field, target in [('Mission name', 'mission'), ('Year', 'year'), ('Month', 'month')]:
                record[target] = values[stripped.index(field)].strip() if field in stripped else None
            if record['year'] and not re.fullmatch(r'\d{4}', record['year']):
                raise ValueError(f'Invalid catalog year at row {line}')
            month = record['month']
            if month and month.lower() not in MONTHS:
                raise ValueError(f'Invalid catalog month at row {line}')
            record['catalog_date'] = record['year'] + ('-' + str(MONTHS[month.lower()]).zfill(2) if month else '') if record['year'] else None
            record['filename_column_ignored'] = True
            rows.append(record)
    return rows, warnings


def validate_case(case):
    required = {'schema_version', 'case_id', 'title', 'mission', 'documents', 'cleaning'}
    if required - case.keys() or case['schema_version'] != 'pkoc-case-v1':
        raise ValueError('Invalid case profile; expected pkoc-case-v1')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', case['case_id']):
        raise ValueError('case_id must be a portable lowercase identifier')
    if 'synthetic_fixture' in case and type(case['synthetic_fixture']) is not bool:
        raise ValueError('synthetic_fixture must be an explicit boolean')
    mission = case['mission']
    if mission.get('language') != 'en' or not mission.get('name'):
        raise ValueError('v1 supports explicitly identified English text only')
    if not isinstance(mission.get('aliases', []), list) or any(not isinstance(a, str) or not a for a in mission.get('aliases', [])):
        raise ValueError('Mission aliases must be nonempty strings')
    if not isinstance(case['documents'], list) or not case['documents']:
        raise ValueError('Select documents explicitly; catalog mission tags do not establish eligibility')
    seen = set()
    for spec in case['documents']:
        symbol = normalize_symbol(spec['symbol'])
        if symbol in seen:
            raise ValueError('Duplicate selected document: ' + symbol)
        seen.add(symbol)
        if type(spec.get('include')) is not bool or not spec.get('eligibility_reason', '').strip():
            raise ValueError('Each selected/excluded document requires include and eligibility_reason')
        parse_partial_date(spec.get('report_date'))
        if spec.get('sha256') and not re.fullmatch('[0-9a-f]{64}', spec['sha256']):
            raise ValueError('Expected source sha256 must be lowercase hexadecimal')
    policy = case.get('literal_policy', {})
    for key, default in (('max_name_codepoints', 160), ('max_attribute_codepoints', 400)):
        integer(policy.get(key, default), key, 1, 4000)
    cleaning = case['cleaning']
    if cleaning.get('mode') not in ('numbered', 'blankline'):
        raise ValueError('Select numbered or explicit blankline cleaning')
    if type(cleaning.get('truncate_annex', True)) is not bool:
        raise ValueError('truncate_annex must be boolean')
    if cleaning.get('paragraph_limit') is not None:
        integer(cleaning['paragraph_limit'], 'paragraph_limit')
    if any(not isinstance(s, str) or not s for s in cleaning.get('stop_headings', [])):
        raise ValueError('stop_headings must be literal nonempty strings')
    return case


def inventory(case, source_root, catalog_path=None):
    validate_case(case)
    source_root = Path(source_root).resolve()
    if not source_root.is_dir():
        raise ValueError('Source directory does not exist')
    indexed = {}
    for path in source_root.rglob('*.txt'):
        match = FILE.fullmatch(path.name)
        if match:
            indexed.setdefault(symbol_from_match(match), []).append(path)
    catalog, warnings = read_catalog(catalog_path)
    selected, excluded = [], []
    for spec in case['documents']:
        symbol = normalize_symbol(spec['symbol'])
        if not spec['include']:
            excluded.append({'document_symbol': symbol, 'reason': spec['eligibility_reason']})
            continue
        matches = indexed.get(symbol, [])
        if len(matches) != 1:
            raise ValueError(f'{symbol}: expected exactly one actual English extraction file; found {len(matches)}')
        path = matches[0]
        raw = path.read_bytes()
        text = raw.decode('utf-8-sig', errors='strict')
        header = text[:4000]
        header_symbols = [symbol_from_match(m) for m in SYMBOL.finditer(header[:1200])]
        if not header_symbols or header_symbols[0] != symbol:
            raise ValueError(f'{symbol}: file/header symbol mismatch or unavailable header symbol')
        header_date = None
        match = DATE.search(header[:2000])
        if match:
            header_date = date(int(match[3]), MONTHS[match[2].lower()], int(match[1])).isoformat()
        else:
            match = MONTH_DATE.search(header[:2000])
            if match:
                header_date = f'{match[2]}-{MONTHS[match[1].lower()]:02d}'
        symbol_rows = [r for r in catalog if r['document_symbol'] == symbol]
        catalog_rows = [r for r in symbol_rows if r['mission'] in [case['mission']['name'], *case['mission'].get('aliases', [])]]
        if symbol_rows and not catalog_rows:
            raise ValueError(f'{symbol}: catalog mission conflicts with selected case mission')
        catalog_dates = {r['catalog_date'] for r in catalog_rows if r['catalog_date']}
        if len(catalog_dates) > 1:
            raise ValueError(f'{symbol}: conflicting catalog dates')
        catalog_date = next(iter(catalog_dates), None)
        dates = [d for d in (header_date, catalog_date, spec.get('report_date')) if d]
        if any(a[:min(len(a), len(b))] != b[:min(len(a), len(b))] for a in dates for b in dates):
            raise ValueError(f'{symbol}: header/catalog/profile date mismatch')
        # An explicit profile date cannot supply finer precision than source metadata.
        available = [d for d in (header_date, catalog_date) if d]
        report_date = max(available, key=len) if available else None
        sha = hashlib.sha256(raw).hexdigest()
        if file_hash(path) != sha:
            raise ValueError('Source changed during inventory capture: ' + symbol)
        if spec.get('sha256') and sha != spec['sha256']:
            raise ValueError(f'{symbol}: source hash mismatch')
        report_id = symbol.replace('/', '_').replace('.', '_')
        selected.append({'report_id': report_id, 'document_symbol': symbol,
                         'source_file': path.relative_to(source_root).as_posix(), 'sha256': sha,
                         'bytes': len(raw), 'report_date': report_date,
                         'date_precision': {4: 'year', 7: 'month', 10: 'day'}.get(len(report_date or ''), 'unknown'),
                         'year': int(report_date[:4]) if report_date else None,
                         'date_sources': [s for s, d in [('header', header_date), ('catalog', catalog_date)] if d],
                         'header_symbol_verified': True, 'catalog_match_count': len(catalog_rows),
                         'eligibility_reason': spec['eligibility_reason'],
                         'official_url': None if case.get('synthetic_fixture', False) else 'https://docs.un.org/en/' + symbol})
    if not selected:
        raise ValueError('At least one document must be explicitly included')
    return {'schema': 'pkoc-inventory-v1', 'reports': selected, 'excluded': excluded,
            'catalog_sha256': file_hash(catalog_path) if catalog_path else None,
            'warnings': warnings, 'selection_is_researcher_supplied': True}


def prepare(case, source_root, inv):
    paragraphs, sentences, cleaning = [], [], []
    rules = case['cleaning']
    for report in inv['reports']:
        path = Path(source_root) / report['source_file']
        captured = path.read_bytes()
        if hashlib.sha256(captured).hexdigest() != report['sha256']:
            raise ValueError('Source changed after inventory: ' + report['document_symbol'])
        raw = captured.decode('utf-8-sig', errors='strict')
        markers, _ = corpus.longest_numbered_sequence(raw)
        slices = []
        if rules['mode'] == 'numbered':
            if not markers:
                raise ValueError('No numbered paragraph chain; choose an explicit blankline profile if appropriate')
            for i, marker in enumerate(markers):
                start = marker.end()
                end = markers[i + 1].start() if i + 1 < len(markers) else len(raw)
                if i + 1 == len(markers):
                    headings = [re.escape(h) for h in rules.get('stop_headings', [])]
                    if rules.get('truncate_annex', True):
                        headings.append(r'Annex(?:[ \t]+(?:[IVXLC]+|\d+))?')
                    if headings:
                        stop = re.search(r'(?im)^[ \t\f]*(?:' + '|'.join(headings) + r')[ \t]*$', raw[start:end])
                        if stop:
                            end = start + stop.start()
                mapped = corpus.mapped_normalize(raw[start:end], start)
                if mapped.text != corpus.normalise_text(raw[start:end]):
                    raise ValueError('Unsupported cross-cluster Unicode normalization')
                mapped = corpus.mapped_clean(mapped)
                if mapped.text:
                    slices.append((int(marker[1]), start, end, mapped))
        else:
            slices = [(i, m.spans[0][0], m.spans[-1][1], m) for i, m in enumerate(corpus.fallback_mapped(raw, corpus), 1)]
        available = len(slices)
        slices = slices[:rules.get('paragraph_limit')]
        if not slices:
            raise ValueError('Cleaning produced no selected paragraphs')
        for number, start, end, mapped in slices:
            pid = f"{report['report_id']}:p{number:04d}"
            p = {'paragraph_id': pid, 'report_id': report['report_id'], 'publication_date': report['report_date'],
                 'number': number, 'text': mapped.text, 'text_sha256': __import__('hashlib').sha256(mapped.text.encode()).hexdigest(),
                 'raw_start': start, 'raw_end': end, 'source_codepoint_spans': mapped.spans}
            paragraphs.append(p)
            for i, (a, b) in enumerate(sentence_spans(mapped.text), 1):
                sentences.append({'sentence_id': f'{pid}:s{i:03d}', 'paragraph_id': pid,
                                  'report_id': report['report_id'], 'start': a, 'end': b})
        cleaning.append({'report_id': report['report_id'], 'available_paragraphs': available,
                         'selected_paragraphs': len(slices), 'mode': rules['mode'],
                         'excluded_by_limit': available - len(slices), 'source_sha256': report['sha256'],
                         'rules_sha256': digest(rules)})
    for report in inv['reports']:
        if file_hash(Path(source_root) / report['source_file']) != report['sha256']:
            raise ValueError('Source changed during canonical preparation')
    return {'schema': 'pkoc-prepared-v1', 'paragraphs': paragraphs, 'sentences': sentences,
            'cleaning': cleaning, 'coordinate_policy': 'paragraph-local zero-based half-open Unicode codepoints',
            'historical_pdf_extraction_reproduced': False}
