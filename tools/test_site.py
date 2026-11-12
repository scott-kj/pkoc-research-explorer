"""Publication boundaries: changed data, extra files and false approval fail."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_site import ROOT, build, scientific_digest
from verify_site import verify

class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = tempfile.TemporaryDirectory(prefix='pkoc-publication-tests-')
        cls.base = Path(cls.storage.name).resolve()
        cls.site = cls.base / 'baseline'
        build(ROOT, cls.site)

    @classmethod
    def tearDownClass(cls):
        cls.storage.cleanup()

    def copy(self, name):
        target = self.base / name
        shutil.copytree(self.site, target)
        return target

    def test_reviewed_snapshot_and_six_networks(self):
        self.assertEqual(verify(self.site)['networks'], 6)

    def test_extra_source_file_is_rejected(self):
        site = self.copy('extra')
        (site / 'report.pdf.txt').write_text('not an allowed website input')
        with self.assertRaisesRegex(ValueError, 'unmanifested'):
            verify(site)

    def test_changed_annotation_bytes_are_rejected(self):
        site = self.copy('data-change')
        data = json.loads((site / 'bundle.json').read_text(encoding='utf-8'))
        data['nodes'][0]['name'] = 'Altered identity'
        (site / 'bundle.json').write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'bytes differ'):
            verify(site)

    def test_changed_zip_is_rejected(self):
        site = self.copy('zip-change')
        with (site / 'downloads/annotations.zip').open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'bytes differ'):
            verify(site)

    def test_output_is_never_overwritten(self):
        original = (self.site / 'manifest.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'new or empty'):
            build(ROOT, self.site)
        self.assertEqual((self.site / 'manifest.json').read_bytes(), original)

    def test_pending_approval_is_not_public_authorization(self):
        publication = json.loads((ROOT / 'publication.json').read_text(encoding='utf-8'))
        if publication['authorized']:
            self.assertTrue(verify(self.site, True)['public_release_authorized'])
        else:
            with self.assertRaisesRegex(ValueError, 'confirmation is pending'):
                verify(self.site, True)

    def test_glossary_is_separate_from_scientific_values(self):
        data = json.loads((self.site / 'bundle.json').read_text(encoding='utf-8'))
        original = scientific_digest(data)
        data['codebook'][0]['definition'] = 'Different display explanation'
        self.assertEqual(scientific_digest(data), original)
        data['claims'][0]['office_literal'] = 'Changed observation'
        self.assertNotEqual(scientific_digest(data), original)

if __name__ == '__main__':
    unittest.main()
