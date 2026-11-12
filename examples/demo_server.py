"""Scripted loopback fixture for learning the pipeline. This is NOT an LLM.

It recognizes only the three fictional names in examples/demo/. It must never
be used to annotate research reports. Original example code: MIT.
"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

MODEL = 'scripted-fictional-demo-not-an-llm'
PEOPLE = {'Orin Kelm': ('Governor', 'GOV'), 'Lina Daro': ('Envoy', 'IGO'), 'Mara Venn': ('Journalist', 'MED')}

def reply(body):
    stage = body['response_format']['json_schema']['name'].removeprefix('pkoc_')
    content = body['messages'][1]['content']
    packet = json.loads(content.split('SOURCE_PACKET_JSON:\n', 1)[1].split('\nRESPONSE_SCHEMA_JSON:', 1)[0])
    value = {'request_id': packet['request_id']}
    if stage == 'extraction':
        value['segments'] = []
        for segment in packet['segments']:
            occurrences = []
            for name in PEOPLE:
                start = 0
                while (start := segment['text'].find(name, start)) >= 0:
                    occurrences.append({'text': name, 'left_context': segment['text'][max(0, start-24):start] or None, 'right_context': None})
                    start += len(name)
            value['segments'].append({'segment_id': segment['segment_id'], 'status': 'complete', 'occurrences': occurrences, 'missing_context': []})
    elif stage == 'resolution':
        value['relations'] = [{'candidate_id': candidate['candidate_id'], 'decision': 'SAME' if packet['target']['surface'] in candidate['names'] else 'DIFFERENT', 'evidence_conflict': False, 'evidence_ids': [e['evidence_id'] for e in packet['evidence']], 'reason': 'Scripted fictional example, not a model prediction'} for candidate in packet['candidates']]
    elif stage == 'offices':
        name = next((n for n in packet['person']['names'] if n in PEOPLE), None)
        office = PEOPLE[name][0] if name else None
        ids = [e['evidence_id'] for e in packet['evidence'] if office and office+' '+name in e['text']]
        value.update(person_id=packet['person']['person_id'], status='SUPPORTED' if ids else 'INSUFFICIENT', claims=[{'claim_id':'c1','role_literal':office,'office_literal':office,'affiliation_literal':None,'capacity_status':'current','evidence_ids':ids}] if ids else [], reason='Scripted fictional example, not a model prediction')
    elif stage == 'cameo':
        value.update(person_id=packet['person']['person_id'], assignments=[{'claim_id':c['claim_id'],'status':'SUPPORTED','role_codes':[next(code for office,code in PEOPLE.values() if office==c['role_literal'])],'specialty_codes':[],'evidence_ids':c['evidence_ids'],'reason':'Scripted fictional example, not a model prediction',**{k:c[k] for k in ('role_literal','office_literal','affiliation_literal')}} for c in packet['claims']])
    else:
        raise ValueError('Unsupported demo stage')
    return {'model':MODEL,'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}],'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}

def profile(endpoint):
    return {'schema_version':'pkoc-provider-v1','backend':'openai-compatible','model':MODEL,'endpoint':endpoint,'api_key_env':'PKOC_DEMO_UNUSED_KEY','capabilities':{'json_schema':True,'seed':False,'thinking':False,'tokenization':'declared-upper-bound','tokens_per_utf8_byte_upper_bound':1,'chat_overhead_tokens':128},'stages':{name:{'input_ceiling':50000,'max_tokens':1024,'context_size':65536,'token_margin':256,'temperature':0} for name in ('extraction','resolution','offices','cameo')},'max_attempts':2,'timeout_seconds':10}

@contextmanager
def served_demo():
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def send_json(self, value, status=200):
            raw=json.dumps(value).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if self.path == '/v1/models': self.send_json({'data':[{'id':MODEL}]})
            else: self.send_json({'error':'Unknown fixture route'},404)
        def do_POST(self):
            if self.path != '/v1/chat/completions': return self.send_json({'error':'Unknown fixture route'},404)
            length=int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 2_000_000: return self.send_json({'error':'Invalid fixture request size'},400)
            body=json.loads(self.rfile.read(length));calls.append(body['response_format']['json_schema']['name'])
            self.send_json(reply(body))
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try: yield f'http://127.0.0.1:{server.server_port}/v1',calls
    finally: server.shutdown();server.server_close();thread.join(3)
