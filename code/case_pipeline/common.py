"""Strict JSON, immutable records, hashing and run-directory ownership."""
from __future__ import annotations
import hashlib
import json
import os
import platform
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / 'protocol' / 'case_pipeline'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate JSON key: ' + key)
            value[key] = item
        return value
    def nonfinite(value):
        raise ValueError('Non-finite JSON number: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=pairs, parse_constant=nonfinite)


def write_json(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if exclusive:
        with path.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(payload)
        return
    temp = path.with_name(path.name + '.pending')
    with temp.open('w', encoding='utf-8', newline='\n') as handle:
        handle.write(payload)
    temp.replace(path)


def utc():
    return datetime.now(timezone.utc).isoformat()


def integer(value, name, minimum=1, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f'{name} must be an integer in [{minimum}, {maximum or "unbounded"}]')
    return value


def validate_schema(value, schema, location='$'):
    kinds = {'object': isinstance(value, dict), 'array': isinstance(value, list),
             'string': isinstance(value, str), 'integer': type(value) is int,
             'number': type(value) in (int, float), 'boolean': type(value) is bool,
             'null': value is None}
    if 'type' in schema and not kinds.get(schema['type'], False):
        raise ValueError(location + ': wrong type')
    if 'enum' in schema and not any(canonical(value) == canonical(v) for v in schema['enum']):
        raise ValueError(location + ': outside enum')
    if 'anyOf' in schema:
        for child in schema['anyOf']:
            try:
                validate_schema(value, child, location)
                break
            except ValueError:
                pass
        else:
            raise ValueError(location + ': no permitted alternative')
    if isinstance(value, dict):
        properties = schema.get('properties', {})
        if set(schema.get('required', [])) - value.keys():
            raise ValueError(location + ': missing fields')
        if schema.get('additionalProperties') is False and value.keys() - properties.keys():
            raise ValueError(location + ': unexpected fields')
        for key in value.keys() & properties.keys():
            validate_schema(value[key], properties[key], location + '.' + key)
    if isinstance(value, list) and 'items' in schema:
        for i, child in enumerate(value):
            validate_schema(child, schema['items'], f'{location}[{i}]')
    if isinstance(value, (str, list)):
        suffix = 'Length' if isinstance(value, str) else 'Items'
        if len(value) < schema.get('min' + suffix, 0) or len(value) > schema.get('max' + suffix, float('inf')):
            raise ValueError(location + ': length outside bounds')


def code_hashes():
    paths = list((ROOT / 'code' / 'case_pipeline').glob('*.py'))
    paths += list(PROTOCOL.glob('*'))
    paths += [ROOT / 'code' / n for n in ('corpus.py', 'segmentation.py', 'inference_components.py', 'explorer_data.py')]
    paths += [ROOT / 'tools' / 'run_case.py', ROOT / 'protocol' / 'codebook.json']
    return {p.relative_to(ROOT).as_posix(): file_hash(p) for p in sorted(paths) if p.is_file()}


def redact(value, secrets=()):
    """Remove credentials from native receipts; private source prose stays local."""
    forbidden = re.compile(r'authorization|api[_-]?key|access[_-]?token|secret|password', re.I)
    if isinstance(value, dict):
        return {k: '[REDACTED]' if forbidden.search(k) else redact(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, '[REDACTED]')
    return value


class RunStore:
    """Only a new directory or an explicitly resumed, unchanged run may be written."""
    def __init__(self, output, binding, resume=False):
        original = Path(output).absolute()
        if any(p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()) for p in (original, *original.parents)):
            raise ValueError('Output path and ancestors must not be symlinks or junctions')
        self.path = original.resolve()
        if self.path == ROOT or self.path in ROOT.parents or (self.path.is_dir() and self.path.is_symlink()):
            raise ValueError('Unsafe output destination')
        self.binding = binding
        self.binding_hash = digest(binding)
        self.lock = self.path / '.run.lock'
        self.state_path = self.path / 'run-state.json'
        if self.path.exists() and any(self.path.iterdir()):
            if not resume or not self.state_path.is_file():
                raise ValueError('Output must be new/empty; use --resume only for an owned run')
            self.state = read_json(self.state_path)
            if self.state.get('binding_sha256') != self.binding_hash:
                raise ValueError('Resume rejected: inputs, configuration, runtime assets, or code changed')
            self.verify()
        else:
            if resume:
                raise ValueError('Cannot resume a nonexistent run')
            self.path.mkdir(parents=True, exist_ok=True)
            self.state = {'schema': 'pkoc-run-v1', 'created_utc': utc(), 'binding': binding,
                          'binding_sha256': self.binding_hash, 'status': 'created', 'stages': {},
                          'artifacts': {}, 'python': sys.version, 'platform': platform.platform()}
        self._fd = None

    def __enter__(self):
        try:
            self._fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise ValueError('Run is locked; verify no process is active before removing a stale .run.lock') from exc
        os.write(self._fd, canonical({'pid': os.getpid(), 'started_utc': utc()}).encode())
        self.save()
        return self

    def __exit__(self, kind, value, trace):
        if kind:
            self.state['status'] = 'interrupted' if issubclass(kind, KeyboardInterrupt) else 'failed'
            self.state['last_error_type'] = kind.__name__
        self.save()
        if self._fd is not None:
            os.close(self._fd)
            self.lock.unlink(missing_ok=True)
        return False

    def save(self):
        self.state['updated_utc'] = utc()
        write_json(self.state_path, self.state)

    def verify(self):
        from .attempts import verify_registry
        if self.state.get('request_registry') is not None:
            verify_registry(self.path / 'private' / 'requests', self.state['request_registry'])
        if digest(self.state['binding']) != self.state['binding_sha256']:
            raise ValueError('Run binding hash mismatch')
        for name, expected in self.state.get('artifacts', {}).items():
            p = self.path / name
            if p.resolve().parent != self.path and self.path not in p.resolve().parents:
                raise ValueError('Artifact escaped run directory')
            if not p.is_file() or file_hash(p) != expected:
                raise ValueError('Run artifact missing or changed: ' + name)

    def write(self, name, value):
        p = self.path / name
        if self.path not in p.resolve().parents:
            raise ValueError('Artifact escaped run directory')
        write_json(p, value)
        self.state['artifacts'][name] = file_hash(p)
        self.save()

    def stage(self, name, status, **details):
        self.state['stages'][name] = {'status': status, 'utc': utc(), **details}
        self.state['status'] = status
        self.save()
