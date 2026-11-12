"""Public onboarding must run without private files, models or external APIs."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'));sys.path.insert(0,str(ROOT/'tools'))
from run_demo import run_demo
from configure_local import configure
from case_pipeline.ingest import validate_case
from case_pipeline.providers import runtime_receipt
from case_pipeline.runner import execute, parser

class PublicToolkitTests(unittest.TestCase):
    def test_complete_scripted_demo_and_public_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'run';receipt=run_demo(output)
            self.assertEqual(receipt['status'],'passed');self.assertEqual(receipt['external_calls'],0)
            bundle=json.loads((output/'bundle.json').read_text(encoding='utf-8'))
            self.assertTrue(bundle['provenance']['synthetic_fixture']);self.assertFalse(bundle['provenance']['human_reviewed'])
            self.assertEqual(bundle['dataset']['rosters'],['L']);self.assertTrue(all(r['official_url'] is None for r in bundle['reports']))
            self.assertEqual({n['name'] for n in bundle['nodes']},{'Orin Kelm','Lina Daro','Mara Venn'})
            prepared=json.loads((output/'prepared.json').read_text(encoding='utf-8'))
            serialized=(output/'bundle.json').read_text(encoding='utf-8')
            self.assertTrue(all(p['text'] not in serialized for p in prepared['paragraphs']))
            before=(output/'bundle.json').read_bytes()
            with self.assertRaisesRegex(ValueError,'new or empty'):run_demo(output)
            self.assertEqual((output/'bundle.json').read_bytes(),before)

    def test_default_run_is_preflight_only_without_contacting_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'not-created'
            args=parser().parse_args(['run','--case',str(ROOT/'examples/demo/case.json'),'--provider',str(ROOT/'config/providers/compatible-api.example.json'),'--sources',str(ROOT/'examples/demo/text'),'--output',str(output),'--max-requests','10'])
            self.assertEqual(execute(args)['status'],'preflight_only');self.assertFalse(output.exists())

    def test_local_setup_hashes_assets_without_execution_and_rejects_added_library(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);runtime=root/'runtime';runtime.mkdir()
            server=runtime/'llama-server';server.write_bytes(b'non-executable fixture, never launched')
            (runtime/'libllama.so.1').write_bytes(b'fictional shared library')
            model=root/'model.gguf';model.write_bytes(b'fictional model')
            template=root/'template.jinja';template.write_text('fictional template',encoding='utf-8')
            out=root/'config';receipt=configure(server,model,template,'fixture','fixture build',out)
            self.assertEqual(receipt['runtime_members'],2)
            profile=json.loads((out/'provider.json').read_text(encoding='utf-8'))
            (runtime/'unlisted.so.2').write_bytes(b'unlisted')
            with self.assertRaisesRegex(ValueError,'Unlisted'):
                runtime_receipt(profile,{'server':server,'model':model,'chat_template':template,'runtime_manifest':out/'runtime.json'})

    def test_fictional_marker_cannot_be_ambiguous(self):
        case=json.loads((ROOT/'examples/demo/case.json').read_text(encoding='utf-8'))
        case['synthetic_fixture']='false'
        with self.assertRaisesRegex(ValueError,'boolean'):validate_case(case)

if __name__=='__main__':unittest.main()
