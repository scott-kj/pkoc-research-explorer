"""Owned llama.cpp and explicitly configured compatible HTTP providers.

Only inference POST attempts consume the execution budget. Health, model identity,
local template rendering and tokenization are separately recorded preflight calls.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import socket
import secrets as secure_random
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from .attempts import AttemptRegistry
from .common import canonical, digest, file_hash, integer, read_json, redact, utc, validate_schema, write_json


class BudgetExhausted(RuntimeError):
    pass


class ContextLimit(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Provider redirects are disabled; configure the intended endpoint explicitly')


def safe_endpoint(value, *, allow_loopback=True):
    parts = urllib.parse.urlsplit(value)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError('Endpoint must not contain credentials, query parameters or fragments')
    loopback = parts.hostname in ('127.0.0.1', 'localhost', '::1')
    if parts.scheme != 'https' and not (parts.scheme == 'http' and loopback and allow_loopback):
        raise ValueError('Remote API endpoints require HTTPS; HTTP is allowed only for loopback fixtures')
    if not parts.hostname:
        raise ValueError('Endpoint has no hostname')
    return value.rstrip('/')


def validate_provider(profile):
    if profile.get('schema_version') != 'pkoc-provider-v1' or profile.get('backend') not in ('llama-local', 'openai-compatible'):
        raise ValueError('Expected pkoc-provider-v1 with an explicit supported backend')
    if not isinstance(profile.get('model'), str) or not profile['model']:
        raise ValueError('Provider model identity is required')
    caps = profile.get('capabilities', {})
    if caps.get('json_schema') is not True:
        raise ValueError('This pipeline requires explicitly declared JSON-schema response support')
    stages = profile.get('stages', {})
    if set(stages) != {'extraction', 'resolution', 'offices', 'cameo'}:
        raise ValueError('All four stage generation profiles must be specified')
    for stage, spec in stages.items():
        for key in ('input_ceiling', 'max_tokens', 'context_size'):
            integer(spec.get(key), stage + '.' + key)
        integer(spec.get('token_margin', 256), stage + '.token_margin', 0)
        if spec['input_ceiling'] + spec['max_tokens'] + spec.get('token_margin', 256) > spec['context_size']:
            raise ValueError('Stage budgets exceed context size: ' + stage)
        if type(spec.get('temperature')) not in (int, float) or spec['temperature'] < 0:
            raise ValueError('Explicit nonnegative temperature is required')
        if 'seed' in spec and (type(spec['seed']) is not int or caps.get('seed') is not True):
            raise ValueError('Seed requested but provider seed capability is unsupported')
        if 'enable_thinking' in spec and (type(spec['enable_thinking']) is not bool or caps.get('thinking') is not True):
            raise ValueError('Thinking setting requested but provider thinking capability is unsupported')
    integer(profile.get('max_attempts', 2), 'max_attempts', 1, 2)
    integer(profile.get('timeout_seconds', 1800), 'timeout_seconds')
    mode = caps.get('tokenization')
    if mode not in ('llama', 'declared-upper-bound'):
        raise ValueError('Explicit llama tokenization or declared-upper-bound capability is required')
    if mode == 'declared-upper-bound':
        integer(caps.get('tokens_per_utf8_byte_upper_bound'), 'tokens_per_utf8_byte_upper_bound')
        integer(caps.get('chat_overhead_tokens'), 'chat_overhead_tokens', 0)
    if profile['backend'] == 'openai-compatible':
        safe_endpoint(profile.get('endpoint', ''))
        if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', profile.get('api_key_env', '')):
            raise ValueError('API credentials must use a named environment variable')
        if caps.get('thinking') and profile.get('thinking_parameter') != 'chat_template_kwargs.enable_thinking':
            raise ValueError('Unsupported thinking parameter; no implicit provider-specific translation')
    return profile


def runtime_receipt(profile, assets):
    """Hash requested assets without starting or contacting an inference provider."""
    validate_provider(profile)
    if profile['backend'] != 'llama-local':
        return {'backend': profile['backend'], 'endpoint': safe_endpoint(profile['endpoint']),
                'model': profile['model'], 'capabilities': profile['capabilities'],
                'credential_present': bool(os.environ.get(profile['api_key_env'])),
                'credential_environment_variable': profile['api_key_env']}
    required = ('model', 'server', 'chat_template', 'runtime_manifest')
    if any(not assets.get(name) for name in required):
        raise ValueError('Local backend requires --model, --server, --chat-template and --runtime-manifest')
    model, server, template = (Path(assets[key]).resolve() for key in ('model', 'server', 'chat_template'))
    manifest = read_json(assets['runtime_manifest'])
    if manifest.get('schema') != 'pkoc-runtime-v1' or not manifest.get('files'):
        raise ValueError('Expected complete verified pkoc-runtime-v1 runtime manifest')
    records, seen = [], set()
    for item in manifest['files']:
        rel = Path(item['file'])
        if rel.is_absolute() or '..' in rel.parts or rel.as_posix().casefold() in seen:
            raise ValueError('Unsafe or duplicate runtime manifest member')
        seen.add(rel.as_posix().casefold())
        path = (server.parent / rel).resolve()
        if server.parent not in path.parents or not path.is_file():
            raise ValueError('Missing runtime member: ' + rel.as_posix())
        actual = file_hash(path)
        if actual != item['sha256']:
            raise ValueError('Runtime member hash mismatch: ' + rel.as_posix())
        records.append({'file': rel.as_posix(), 'sha256': actual})
    if server.name.casefold() not in seen:
        raise ValueError('Server executable is not pinned by the runtime manifest')
    for path in server.parent.rglob('*'):
        if (path.suffix.lower() in ('.exe', '.dll', '.so', '.dylib') or '.so.' in path.name.lower()) and path.is_file():
            rel = path.relative_to(server.parent)
            if rel.parts[0].casefold() == 'archives':
                continue
            if rel.as_posix().casefold() not in seen:
                raise ValueError('Unlisted executable/runtime dependency: ' + rel.as_posix())
    model_hash, template_hash = file_hash(model), file_hash(template)
    if model_hash != profile.get('model_sha256') or template_hash != profile.get('chat_template_sha256'):
        raise ValueError('Model or chat-template hash differs from provider profile')
    return {'backend': 'llama-local', 'model': profile['model'], 'model_sha256': model_hash,
            'chat_template_sha256': template_hash, 'runtime_files': sorted(records, key=lambda r: r['file']),
            'runtime_manifest_sha256': file_hash(assets['runtime_manifest']),
            'engine_build': profile.get('engine_build'), 'capabilities': profile['capabilities']}


class CompatibleBackend:
    def __init__(self, profile, *, endpoint=None, credential=None):
        self.profile = validate_provider(profile)
        self.endpoint = safe_endpoint(endpoint or profile.get('endpoint', 'http://127.0.0.1:1'))
        self.credential = credential if credential is not None else os.environ.get(profile.get('api_key_env', ''), '')
        self.secrets = (self.credential,)
        self.opener = urllib.request.build_opener(NoRedirect())
        self.receipt = {'backend': profile['backend'], 'endpoint': self.endpoint, 'model': profile['model'],
                        'capabilities': profile['capabilities'], 'preflight': []}

    def http(self, path, body=None, timeout=None):
        headers = {'Accept': 'application/json'}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        if self.credential:
            headers['Authorization'] = 'Bearer ' + self.credential
        req = urllib.request.Request(self.endpoint + path, data=canonical(body).encode() if body is not None else None,
                                     headers=headers, method='POST' if body is not None else 'GET')
        try:
            with self.opener.open(req, timeout=timeout or self.profile.get('timeout_seconds', 1800)) as response:
                raw = response.read(64 * 1024 * 1024 + 1)
                if len(raw) > 64 * 1024 * 1024:
                    raise ValueError('Provider response exceeds 64 MiB')
                def pairs(items):
                    value = {}
                    for key, item in items:
                        if key in value:
                            raise ValueError('Duplicate native response key')
                        value[key] = item
                    return value
                def nonfinite(value):
                    raise ValueError('Nonfinite native response number')
                try:
                    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
                except (ValueError, UnicodeError) as exc:
                    failure = {'native_json_error': str(exc), 'raw_body': raw.decode('utf8', errors='replace')}
                    raise RuntimeError(canonical(redact(failure, self.secrets))) from None
        except urllib.error.HTTPError as exc:
            # Preserve a bounded native error body without headers or secrets.
            body = exc.read(65536).decode('utf8', errors='replace')
            raise RuntimeError(canonical(redact({'http_status': exc.code, 'body': body}, self.secrets))) from None

    def __enter__(self):
        if self.profile['backend'] == 'openai-compatible' and not self.credential:
            raise ValueError('Provider API credential environment variable is unset')
        model_path = self.profile.get('models_path', '/models')
        response = self.http(model_path, timeout=30)
        models = [row.get('id') for row in response.get('data', [])]
        if self.profile['model'] not in models:
            raise ValueError('Configured model is not advertised by provider /models')
        self.receipt['preflight'].append({'kind': 'models', 'response': redact(response, self.secrets), 'utc': utc()})
        return self

    def __exit__(self, *args):
        return False

    def count_tokens(self, messages, settings=None):
        caps = self.profile['capabilities']
        if caps['tokenization'] == 'llama':
            rendered = self.http(self.profile.get('apply_template_path', '/apply-template'), {'messages': messages, **({'chat_template_kwargs': {'enable_thinking': settings['enable_thinking']}} if settings and 'enable_thinking' in settings else {})})
            if not isinstance(rendered.get('prompt'), str):
                raise ValueError('Provider did not return a rendered chat template')
            tokens = self.http(self.profile.get('tokenize_path', '/tokenize'), {'content': rendered['prompt'], 'add_special': True})
            if not isinstance(tokens.get('tokens'), list):
                raise ValueError('Provider did not return token IDs')
            return len(tokens['tokens']), 'rendered-template-tokenizer'
        # The operator explicitly declares this conservative bound for this provider.
        # It is not represented as a tokenizer measurement or provider equivalence.
        return (len(canonical(messages).encode()) * caps['tokens_per_utf8_byte_upper_bound'] + caps['chat_overhead_tokens'],
                'operator-declared-upper-bound')

    def payload(self, stage, messages, schema):
        settings = self.profile['stages'][stage]
        count, method = self.count_tokens(messages, settings)
        if count > settings['input_ceiling'] or count + settings['max_tokens'] + settings.get('token_margin', 256) > settings['context_size']:
            raise ContextLimit(f'{stage}: input {count} ({method}) exceeds configured context budget')
        body = {'model': self.profile['model'], 'messages': messages,
                'temperature': settings['temperature'], 'max_tokens': settings['max_tokens'],
                'response_format': {'type': 'json_schema', 'json_schema': {'name': 'pkoc_' + stage, 'strict': True, 'schema': schema}}}
        if 'seed' in settings:
            body['seed'] = settings['seed']
        if 'enable_thinking' in settings:
            body['chat_template_kwargs'] = {'enable_thinking': settings['enable_thinking']}
        return body, {'input_tokens': count, 'input_measurement': method, 'settings': settings}

    def complete(self, body):
        return self.http(self.profile.get('chat_path', '/chat/completions'), body)


class LocalBackend(CompatibleBackend):
    def __init__(self, profile, assets, run_dir, verified):
        super().__init__(profile, credential='')
        self.assets, self.run_dir, self.verified = assets, Path(run_dir), verified
        self.process, self.log = None, None

    def __enter__(self):
        # All assets were hashed for the run binding immediately before this launch.
        # Recheck small runtime/template files here to reject replacement before startup.
        server = Path(self.assets['server']).resolve()
        for record in self.verified['runtime_files']:
            if file_hash(server.parent / record['file']) != record['sha256']:
                raise ValueError('Runtime asset changed before launch')
        if file_hash(self.assets['chat_template']) != self.verified['chat_template_sha256']:
            raise ValueError('Chat template changed before launch')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.endpoint = f'http://127.0.0.1:{port}'
        runtime = self.profile.get('runtime', {})
        args = [str(server), '--model', str(Path(self.assets['model']).resolve()),
                '--chat-template-file', str(Path(self.assets['chat_template']).resolve()), '--jinja',
                '--host', '127.0.0.1', '--port', str(port), '--alias', self.profile['model'],
                '--ctx-size', str(max(s['context_size'] for s in self.profile['stages'].values())),
                '--n-gpu-layers', str(integer(runtime.get('gpu_layers', 0), 'gpu_layers', 0)),
                '--threads', str(integer(runtime.get('threads', 1), 'threads')),
                '--batch-size', str(integer(runtime.get('batch_size', 256), 'batch_size')),
                '--ubatch-size', str(integer(runtime.get('ubatch_size', 128), 'ubatch_size')),
                '--parallel', '1', '--cors-origins', 'localhost', '--no-cors-credentials', '--no-webui', '--no-agent']
        self.credential = secure_random.token_urlsafe(32)
        self.secrets = (self.credential,)
        child_env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('LLAMA_ARG_', 'LLAMA_API_KEY'))}
        child_env['LLAMA_API_KEY'] = self.credential
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        self.run_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.run_dir / ('server-' + str(time.time_ns()) + '.log')
        self.log = log_path.open('x', encoding='utf8')
        try:
            self.process = subprocess.Popen(args, cwd=server.parent, stdout=self.log, stderr=subprocess.STDOUT,
                                            creationflags=flags, stdin=subprocess.DEVNULL, env=child_env)
            self.receipt.update({'endpoint': self.endpoint, 'owned_pid': self.process.pid,
                                 'verified_assets': self.verified, 'launch_settings': runtime,
                                 'started_utc': utc(), 'log': log_path.name, 'ephemeral_api_authentication': True,
                                 'cors_policy': 'localhost', 'web_ui': False, 'inherited_llama_settings_removed': True})
            deadline = time.monotonic() + self.profile.get('startup_timeout_seconds', 600)
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError('Owned llama.cpp process exited during startup; inspect local server log')
                try:
                    health = self.http('/health', timeout=2)
                    if health.get('status') == 'ok':
                        self.receipt['preflight'].append({'kind': 'health', 'response': health, 'utc': utc()})
                        break
                except (OSError, ValueError, RuntimeError):
                    pass
                time.sleep(0.5)
            else:
                raise TimeoutError('Owned llama.cpp startup deadline exceeded')
            models = self.http('/v1/models', timeout=10)
            if self.profile['model'] not in [r.get('id') for r in models.get('data', [])]:
                raise ValueError('Owned llama.cpp advertised unexpected model alias')
            self.receipt['preflight'].append({'kind': 'models', 'response': models, 'utc': utc()})
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        if self.log is not None:
            self.log.close()
        self.receipt['stopped_utc'] = utc()
        self.receipt['exit_code'] = self.process.returncode if self.process else None
        return False

    def complete(self, body):
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError('Owned llama.cpp process is unavailable')
        return self.http('/v1/chat/completions', body)


class RequestStore:
    """Immutable starts/completions make interrupted calls count against the cap."""
    def __init__(self, path, backend, max_requests, owner=None):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.backend = backend
        self.max_requests = integer(max_requests, 'max_requests')
        self.events = []
        self.registry = AttemptRegistry(self.path, owner=owner)
        if self.attempt_count > self.max_requests:
            raise ValueError('Existing attempts exceed configured cap')

    @property
    def attempt_count(self):
        return self.registry.count

    def request(self, stage, packet, prompt, schema, semantic_validator):
        rid = packet['request_id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', rid):
            raise ValueError('Unsafe request ID')
        messages = [{'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': 'SOURCE_PACKET_JSON:\n' + canonical(packet) + '\nRESPONSE_SCHEMA_JSON:\n' + canonical(schema)}]
        key = digest({'stage': stage, 'messages': messages, 'schema': schema,
                      'settings': self.backend.profile['stages'][stage], 'provider': self.backend.profile})
        existing = self.registry.for_request(rid)
        for record in existing:
            if record['logical_sha256'] != key:
                raise ValueError('Request ID reused with different inputs/settings')
            finish = self.path / (record['name'] + '.finish.json')
            if finish.exists():
                result = read_json(finish)
                if result['outcome'] == 'accepted':
                    value = json.loads(result['native_response']['choices'][0]['message']['content'])
                    if value != result['parsed']:
                        raise ValueError('Cached parsed response differs from native response')
                    validate_schema(value, schema)
                    semantic_validator(value)
                    self.events.append({'request_id': rid, 'stage': stage, 'status': 'cached'})
                    return value
        max_attempts = self.backend.profile.get('max_attempts', 2)
        if len(existing) >= max_attempts:
            self.events.append({'request_id': rid, 'stage': stage, 'status': 'failed'})
            return None
        try:
            payload, token_receipt = self.backend.payload(stage, messages, schema)
        except ContextLimit as exc:
            self.events.append({'request_id': rid, 'stage': stage, 'status': 'excluded_context_limit', 'detail': str(exc)})
            return None
        for attempt in range(len(existing) + 1, max_attempts + 1):
            if self.attempt_count >= self.max_requests:
                raise BudgetExhausted('Inference request-attempt cap reached')
            name = f'{rid}-{attempt:02d}'
            start_path = self.path / (name + '.start.json')
            start = {'request_id': rid, 'stage': stage, 'attempt': attempt, 'started_utc': utc(),
                     'logical_sha256': key, 'request': payload, 'request_sha256': digest(payload),
                     'token_receipt': token_receipt}
            start = redact(start, self.backend.secrets)
            start['request_sha256'] = digest(start['request'])
            reservation = self.registry.reserve(start)
            write_json(start_path, start, exclusive=True)
            self.registry.started(reservation)
            began = time.monotonic()
            native, parsed, error, outcome = None, None, None, 'failed'
            try:
                native = self.backend.complete(payload)
                try:
                    canonical(native)
                except (ValueError, TypeError):
                    native = {'unserializable_native_response': repr(native)[:65536]}
                    raise ValueError('Provider native response must be finite JSON')
                if not isinstance(native, dict):
                    raise ValueError('Provider native envelope must be an object')
                choices = native.get('choices')
                if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict) or choices[0].get('finish_reason') not in ('stop', 'eos'):
                    raise ValueError('Expected one complete non-truncated response')
                message = choices[0].get('message')
                if not isinstance(message, dict):
                    raise ValueError('Provider message must be an object')
                content = message.get('content')
                if not isinstance(content, str):
                    raise ValueError('Provider final content must be a JSON string')
                def pairs(items):
                    result = {}
                    for k, v in items:
                        if k in result:
                            raise ValueError('Duplicate response JSON key')
                        result[k] = v
                    return result
                parsed = json.loads(content, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite response')))
                validate_schema(parsed, schema)
                semantic_validator(parsed)
                outcome = 'accepted'
            except (ValueError, KeyError, TypeError, RuntimeError, OSError, TimeoutError) as exc:
                error = {'type': type(exc).__name__, 'message': str(exc)}
            except BaseException:
                # The immutable start remains an interrupted consumed attempt.
                raise
            native = redact(native, self.backend.secrets)
            finish = {'request_id': rid, 'attempt': attempt, 'start_sha256': file_hash(start_path),
                      'finished_utc': utc(), 'runtime_seconds': time.monotonic() - began,
                      'outcome': outcome, 'native_response': native, 'response_sha256': digest(native),
                      'parsed': redact(parsed, self.backend.secrets), 'error': redact(error, self.backend.secrets)}
            finish_path = self.path / (name + '.finish.json')
            write_json(finish_path, finish, exclusive=True)
            self.registry.finished(reservation, finish_path)
            if outcome == 'accepted':
                self.events.append({'request_id': rid, 'stage': stage, 'status': 'accepted'})
                return parsed
        self.events.append({'request_id': rid, 'stage': stage, 'status': 'failed'})
        return None
