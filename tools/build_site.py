"""Build the public explorer from its reviewed structured-data snapshot."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
from explorer_data import json_bytes, validate_bundle, write_bundle

SCIENTIFIC_KEYS = ('schema', 'dataset', 'reports', 'nodes', 'occurrences', 'claims',
                   'attributes', 'paragraphs', 'sentences', 'interventions',
                   'correspondence', 'reference_units', 'networks')
STATIC = ('LICENSE', 'LICENSE-DATA.md', 'NOTICES.md', 'CITATION.cff', 'publication.json')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def scientific_digest(bundle):
    return digest(json_bytes({k: bundle[k] for k in SCIENTIFIC_KEYS}))

def build(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or output.is_relative_to(root / 'data') or output.is_relative_to(root / 'web'):
        raise ValueError('Output must be a separate new build directory')
    publication_bytes = (root / 'publication.json').read_bytes()
    publication = json.loads(publication_bytes)
    data = (root / 'data/bundle.json').read_bytes()
    bundle = json.loads(data)
    validate_bundle(bundle)
    if digest(data) != publication['bundle_sha256'] or scientific_digest(bundle) != publication['scientific_data_sha256']:
        raise ValueError('Reviewed annotation snapshot differs; publication review must be explicit')
    before = {name: (root / name).read_bytes() for name in STATIC}
    result = write_bundle(bundle, output, root / 'web')
    result.update(status='reviewed_explorer_publication' if publication['authorized'] else 'reviewed_explorer_candidate',
                  public_release_authorized=publication['authorized'],
                  publication_scope='Structured annotations and explorer only; no archived source prose or manuscript.',
                  upstream_commit=publication['upstream_commit'],
                  scientific_data_sha256=publication['scientific_data_sha256'])
    for name, payload in {**before, '.nojekyll': b''}.items():
        (output / name).write_bytes(payload)
        result['files'].append({'path': name, 'sha256': digest(payload), 'bytes': len(payload)})
    result['files'].sort(key=lambda row: row['path'])
    (output / 'manifest.json').write_bytes(json_bytes(result))
    if (root / 'data/bundle.json').read_bytes() != data or any((root / k).read_bytes() != v for k, v in before.items()):
        raise ValueError('Publication input changed during build')
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'site')
    args = parser.parse_args()
    try:
        record = build(ROOT, args.output)
        print(json.dumps({'status': record['status'], 'files': len(record['files']),
                          'bundle_sha256': record['bundle_sha256']}))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f'Build rejected: {error}\n')
