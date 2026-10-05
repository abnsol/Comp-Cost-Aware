"""Cleanup must preserve original source identity without masking tampering."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from pln_cost.provenance import verify_project_sources


class ProvenanceTests(unittest.TestCase):
    def test_missing_live_source_fails_for_new_batch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            with self.assertRaises(FileNotFoundError):
                verify_project_sources(p,p,{'missing.py':'anything'})

    def test_archive_preserves_historical_hash_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);archive=p/'source-snapshot.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('obsolete.py',b'original')
            (p/'source-snapshot.json').write_text(json.dumps({'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
            expected={'obsolete.py':hashlib.sha256(b'original').hexdigest()}
            self.assertEqual(verify_project_sources(p,p,expected),'archived original source')
            with self.assertRaisesRegex(ValueError,'historical source'):
                verify_project_sources(p,p,{'obsolete.py':hashlib.sha256(b'changed').hexdigest()})
            archive.write_bytes(archive.read_bytes()+b'tampered')
            with self.assertRaisesRegex(ValueError,'archive'):
                verify_project_sources(p,p,expected)

    def test_original_batch_source_snapshot_and_analysis_script(self):
        root=PROJECT/'results/benefit-benchmark/run001'
        frozen=json.loads((root/'freeze.json').read_text())
        self.assertEqual(verify_project_sources(PROJECT,root,frozen['project_sources']),'archived original source')
        with zipfile.ZipFile(root/'source-snapshot.zip') as z:
            script=z.read('scripts/analyze_benefit_benchmark.py')
        analysis=json.loads((root/'measurement/verified-analysis.json').read_text())
        self.assertEqual(hashlib.sha256(script).hexdigest(),analysis['analysis_script_sha256'])


if __name__=='__main__':unittest.main()
