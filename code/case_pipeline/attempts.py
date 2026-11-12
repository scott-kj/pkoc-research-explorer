"""Durable attempt reservations anchored outside removable request receipts."""
from pathlib import Path
from .common import digest, file_hash, read_json, write_json


def verify_registry(path, registry, *, recover=False):
    """Verify deletion/tamper/orphan safety, allowing documented crash boundaries.

    A reserved attempt without a start consumed budget before a crash. A finish
    written after an indexed start but before the registry update can be recovered.
    Neither case permits reusing the reservation or returning budget to the cap.
    """
    path = Path(path)
    if registry.get('schema') != 'pkoc-attempt-registry-v1' or not isinstance(registry.get('attempts'), list):
        raise ValueError('Invalid durable attempt registry')
    records = registry['attempts']
    if registry.get('total_reserved') != len(records):
        raise ValueError('Durable attempt counter/registry mismatch')
    expected, seen, changed = set(), set(), False
    for ordinal, record in enumerate(records, 1):
        name = record['name']
        if '/' in name or '\\' in name or name in seen or record.get('ordinal') != ordinal:
            raise ValueError('Unsafe, duplicate or reordered attempt registry entry')
        seen.add(name)
        start_path, finish_path = path / (name + '.start.json'), path / (name + '.finish.json')
        expected.update((start_path.name, finish_path.name))
        phase = record.get('phase')
        if phase not in ('reserved', 'started', 'finished'):
            raise ValueError('Unknown attempt registry phase')
        if not start_path.exists():
            if phase != 'reserved' or finish_path.exists():
                raise ValueError('Missing indexed start receipt: ' + name)
            continue
        start = read_json(start_path)
        if digest(start) != record['start_value_sha256'] or digest(start['request']) != start['request_sha256']:
            raise ValueError('Indexed start receipt hash mismatch: ' + name)
        if start['logical_sha256'] != record['logical_sha256'] or start['request_id'] != record['request_id']:
            raise ValueError('Indexed request identity mismatch')
        if phase == 'reserved' and recover:
            record['phase'] = 'started'
            phase, changed = 'started', True
        if not finish_path.exists():
            if phase == 'finished':
                raise ValueError('Missing indexed finish receipt: ' + name)
            continue
        finish = read_json(finish_path)
        if finish['start_sha256'] != file_hash(start_path) or digest(finish['native_response']) != finish['response_sha256']:
            raise ValueError('Indexed native response hash mismatch: ' + name)
        if finish['request_id'] != record['request_id'] or finish['attempt'] != start['attempt']:
            raise ValueError('Finish receipt request/attempt mismatch')
        if phase == 'finished':
            if file_hash(finish_path) != record.get('finish_sha256'):
                raise ValueError('Indexed finish receipt hash mismatch: ' + name)
        elif recover:
            record['finish_sha256'] = file_hash(finish_path)
            record['phase'] = 'finished'
            changed = True
    actual = {p.name for p in path.glob('*.start.json')} | {p.name for p in path.glob('*.finish.json')}
    if actual - expected:
        raise ValueError('Orphan request receipt has no durable reservation: ' + sorted(actual - expected)[0])
    return changed


class AttemptRegistry:
    def __init__(self, path, owner=None):
        self.path, self.owner = Path(path), owner
        # Standalone library tests retain a separate checkpoint outside the receipt
        # directory. Production always anchors the registry in RunStore.run-state.
        self.checkpoint = self.path.parent / (self.path.name + '.attempt-registry.json')
        if owner is not None:
            if self.path.resolve() != (owner.path / 'private' / 'requests').resolve():
                raise ValueError('Production request registry must belong to its run')
            self.data = owner.state.get('request_registry')
        else:
            self.data = read_json(self.checkpoint) if self.checkpoint.exists() else None
        if self.data is None:
            if any(self.path.glob('*.start.json')) or any(self.path.glob('*.finish.json')):
                raise ValueError('Existing receipts have no durable registry; start a new owned run')
            self.data = {'schema': 'pkoc-attempt-registry-v1', 'total_reserved': 0, 'attempts': []}
            self.save()
        if verify_registry(self.path, self.data, recover=True):
            self.save()

    def save(self):
        if self.owner is not None:
            self.owner.state['request_registry'] = self.data
            self.owner.save()
        else:
            write_json(self.checkpoint, self.data)

    @property
    def count(self):
        return self.data['total_reserved']

    def for_request(self, request_id):
        return [r for r in self.data['attempts'] if r['request_id'] == request_id]

    def reserve(self, start):
        name = f"{start['request_id']}-{start['attempt']:02d}"
        if any(r['name'] == name for r in self.data['attempts']):
            raise ValueError('Attempt reservation cannot be reused')
        record = {'name': name, 'ordinal': self.count + 1, 'request_id': start['request_id'],
                  'logical_sha256': start['logical_sha256'], 'start_value_sha256': digest(start),
                  'phase': 'reserved', 'reserved_utc': start['started_utc']}
        self.data['attempts'].append(record)
        self.data['total_reserved'] += 1
        self.save()  # Durable budget consumption precedes the start file and POST.
        return record

    def started(self, record):
        record['phase'] = 'started'
        self.save()

    def finished(self, record, finish_path):
        record['finish_sha256'] = file_hash(finish_path)
        record['phase'] = 'finished'
        self.save()
