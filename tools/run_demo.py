#!/usr/bin/env python3
"""Run the complete pipeline with original fictional text and scripted replies.

No model, credentials, external connection, or paid API is used. This example
checks engineering behavior, not model accuracy. Use run_case.py for research.
"""
from pathlib import Path
import argparse
import json
import os
import secrets
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
sys.path.insert(0,str(ROOT/'examples'))
from case_pipeline.runner import execute, parser
from demo_server import profile, served_demo

def run_demo(output):
    output=Path(output).absolute()
    if output.exists() and any(output.iterdir()): raise ValueError('Demo output must be new or empty; choose another --output')
    old_key=os.environ.pop('PKOC_DEMO_UNUSED_KEY',None)
    os.environ['PKOC_DEMO_UNUSED_KEY']=secrets.token_urlsafe(24)
    try:
        with served_demo() as (endpoint,calls), tempfile.TemporaryDirectory(prefix='pkoc-demo-profile-') as temp:
            provider=Path(temp)/'provider.json';provider.write_text(json.dumps(profile(endpoint)),encoding='utf-8')
            args=parser().parse_args(['run','--case',str(ROOT/'examples/demo/case.json'),'--provider',str(provider),'--sources',str(ROOT/'examples/demo/text'),'--output',str(output),'--max-requests','50','--execute'])
            result=execute(args)
        bundle=json.loads((output/'bundle.json').read_text(encoding='utf-8'))
        assert result['status']=='complete',result['status']
        assert len(bundle['nodes'])==3
        graphs={g['scale']:g for g in bundle['networks']}
        assert len(graphs['paragraph']['edges'])==1 and graphs['paragraph']['edges'][0]['weight']==2
        assert graphs['paragraph']['summary']['isolates']==1
        assert len(graphs['report']['edges'])==3
        assert all(r['official_url'] is None for r in bundle['reports'])
        return {'status':'passed','demonstration':'Scripted fictional fixture; no LLM inference or research findings','external_calls':0,'fixture_requests':len(calls),'paragraphs':len(bundle['paragraphs']),'actors':len(bundle['nodes']),'paragraph_network':graphs['paragraph']['summary'],'bundle':str(output/'bundle.json'),'explorer':str(next((output/'exports').glob('*/index.html')))}
    finally:
        os.environ.pop('PKOC_DEMO_UNUSED_KEY',None)
        if old_key is not None: os.environ['PKOC_DEMO_UNUSED_KEY']=old_key

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,default=ROOT/'runs/demo');args=cli.parse_args()
    try: print(json.dumps(run_demo(args.output),indent=2))
    except (ValueError,OSError,AssertionError) as error: cli.exit(1,f'Demo rejected: {error}\n')
