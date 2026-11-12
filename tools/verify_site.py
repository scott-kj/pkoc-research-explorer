"""Verify the complete website allowlist, snapshot, downloads and projections."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
from explorer_data import validate_bundle, project_network
from build_site import scientific_digest

def verify(site, require_approval=False):
    site = Path(site).resolve()
    manifest = json.loads((site / 'manifest.json').read_text(encoding='utf-8'))
    rows = manifest['files']
    names = {row['path'] for row in rows}
    if len(names) != len(rows):
        raise ValueError('Duplicate website manifest path')
    allowed_root = {'index.html', 'app.js', 'core.js', 'graph.js', 'export.js', 'styles.css', 'light.css', 'theme.js', 'favicon.svg', 'bundle.js', 'bundle.json',
                    'LICENSE', 'LICENSE-DATA.md', 'NOTICES.md', 'CITATION.cff', 'publication.json', '.nojekyll'}
    actual = set()
    for path in site.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlink in website')
        if path.is_file():
            actual.add(path.relative_to(site).as_posix())
    if actual != names | {'manifest.json'}:
        raise ValueError('Website contains missing or unmanifested files')
    for row in rows:
        name = row['path']
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name:
            raise ValueError('Unsafe website path')
        if name not in allowed_root and not (len(p.parts) == 2 and p.parts[0] == 'downloads' and p.suffix in {'.csv', '.json', '.graphml', '.zip'}):
            raise ValueError('Path is outside website allowlist')
        data = (site / name).read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Website bytes differ: ' + name)
    payload = (site / 'bundle.json').read_bytes()
    bundle = json.loads(payload)
    validate_bundle(bundle)
    approval = json.loads((site / 'publication.json').read_text(encoding='utf-8'))
    if hashlib.sha256(payload).hexdigest() != approval['bundle_sha256'] or scientific_digest(bundle) != approval['scientific_data_sha256']:
        raise ValueError('Publication snapshot differs')
    if manifest['public_release_authorized'] is not approval['authorized']:
        raise ValueError('Publication authorization declarations disagree')
    if require_approval and not approval['authorized']:
        raise ValueError('Author publication confirmation is pending')
    wrapper = ('window.PKOC_BUNDLE = ' + payload.decode('utf-8').rstrip().replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029') + ';\n').encode('utf-8')
    if (site / 'bundle.js').read_bytes() != wrapper:
        raise ValueError('Browser bootstrap differs from downloadable JSON')
    expected = {('L','sentence'):116, ('A','sentence'):128, ('L','paragraph'):186,
                ('A','paragraph'):196, ('L','report'):929, ('A','report'):887}
    for saved in bundle['networks']:
        graph = project_network(bundle, saved['workflow'], saved['scale'])
        for key in ('edges', 'incidences', 'summary', 'exclusions'):
            if graph[key] != saved[key]:
                raise ValueError('Scientific network difference: ' + key)
        if len(graph['edges']) != expected.pop((saved['workflow'], saved['scale'])):
            raise ValueError('Published edge count differs')
        if [(n['actor_id'], n['degree'], n['strength']) for n in graph['nodes']] != [(n['actor_id'], n['degree'], n['strength']) for n in saved['nodes']]:
            raise ValueError('Roster/isolate/degree/strength differs')
    if expected:
        raise ValueError('Missing baseline network')
    with zipfile.ZipFile(site / 'downloads/annotations.zip') as archive:
        expected_zip = {'bundle.json'} | {n for n in names if n.startswith('downloads/') and not n.endswith('.zip')}
        if set(archive.namelist()) != expected_zip or len(archive.namelist()) != len(expected_zip) or archive.testzip():
            raise ValueError('Unexpected download archive content')
        for name in archive.namelist():
            if archive.read(name) != (site / name).read_bytes():
                raise ValueError('Download archive differs from displayed dataset')
    for filename in ('index.html', 'app.js'):
        source = (site / filename).read_text(encoding='utf-8')
        if 'unmil-annotation-network/blob/' in source or 'tools/run_case.py' in source or 'python run.py' in source:
            raise ValueError('Public interface points to unavailable private instructions')
    return {'status':'passed', 'files':len(rows), 'networks':6, 'public_release_authorized':approval['authorized'],
            'bundle_sha256':approval['bundle_sha256'], 'scientific_data_sha256':approval['scientific_data_sha256']}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site', type=Path)
    parser.add_argument('--require-public-approval', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.site, args.require_public_approval)))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f'Verification rejected: {error}\n')
