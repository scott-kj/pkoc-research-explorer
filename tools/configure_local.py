#!/usr/bin/env python3
"""Create a local provider profile from researcher-verified llama.cpp assets.

This records file integrity, not publisher authenticity. Independently verify
the runtime, GGUF and template before using this helper. It never launches them.
"""
from pathlib import Path
import argparse
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
from case_pipeline.common import file_hash, integer, write_json
from case_pipeline.providers import runtime_receipt

def configure(server,model,template,model_id,engine_build,output,gpu_layers=0,threads=4):
    server,model,template=(Path(p).resolve(strict=True) for p in (server,model,template))
    output=Path(output).absolute()
    if output.exists() and any(output.iterdir()): raise ValueError('Configuration output must be new or empty')
    if output==server.parent or server.parent in output.parents: raise ValueError('Configuration output must be outside the runtime directory')
    integer(gpu_layers,'gpu_layers',0);integer(threads,'threads')
    files=[]
    for file in sorted(server.parent.rglob('*')):
        if not file.is_file() or file.relative_to(server.parent).parts[0].casefold()=='archives': continue
        if server.parent not in file.resolve().parents: raise ValueError('Runtime link leaves the selected runtime directory')
        files.append({'file':file.relative_to(server.parent).as_posix(),'sha256':file_hash(file)})
    manifest={'schema':'pkoc-runtime-v1','files':files,'verification_note':'Researcher-selected assets; these recorded digests do not establish authenticity.'}
    profile={'schema_version':'pkoc-provider-v1','backend':'llama-local','model':model_id,'model_sha256':file_hash(model),'chat_template_sha256':file_hash(template),'engine_build':engine_build,'capabilities':{'json_schema':True,'seed':False,'thinking':False,'tokenization':'llama'},'stages':{stage:{'input_ceiling':12000,'max_tokens':3072,'context_size':16384,'token_margin':256,'temperature':0} for stage in ('extraction','resolution','offices','cameo')},'max_attempts':2,'timeout_seconds':1800,'startup_timeout_seconds':600,'runtime':{'gpu_layers':gpu_layers,'threads':threads,'batch_size':256,'ubatch_size':128},'configuration_note':'Generic starting profile. Verify model context, template and schema support; change settings before creating a run. Thinking and seed controls are not sent.'}
    output.mkdir(parents=True,exist_ok=True)
    manifest_path=output/'runtime.json';profile_path=output/'provider.json'
    write_json(manifest_path,manifest);write_json(profile_path,profile)
    receipt=runtime_receipt(profile,{'model':model,'server':server,'chat_template':template,'runtime_manifest':manifest_path})
    return {'status':'configured','provider':str(profile_path),'runtime_manifest':str(manifest_path),'runtime_members':len(receipt['runtime_files']),'note':'No software was launched. Verify runtime flags and model capabilities before execution.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('server','model','chat-template','output'): p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--model-id',required=True);p.add_argument('--engine-build',required=True);p.add_argument('--gpu-layers',type=int,default=0);p.add_argument('--threads',type=int,default=4)
    a=p.parse_args()
    try: print(json.dumps(configure(a.server,a.model,a.chat_template,a.model_id,a.engine_build,a.output,a.gpu_layers,a.threads),indent=2))
    except (ValueError,OSError) as error: p.exit(1,f'Configuration rejected: {error}\n')
