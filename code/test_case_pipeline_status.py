"""Status queries must not promote a completed stage or stale lock to a full run."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from case_pipeline.common import write_json
from case_pipeline.runner import execute, parser, status_summary


class StatusTests(unittest.TestCase):
    def state(self, stages=('inventory', 'prepare'), recorded='complete'):
        return {'schema': 'pkoc-run-v1', 'status': recorded, 'binding_sha256': 'a' * 64,
                'created_utc': '2026-01-01T00:00:00+00:00', 'updated_utc': '2026-01-01T00:01:00+00:00',
                'stages': {stage: {'status': 'complete', 'scope': stage} for stage in stages}}

    def test_preparation_complete_is_prepared_not_full_run(self):
        state = self.state()
        result = status_summary(state, False)
        self.assertEqual(result['status'], 'prepared')
        self.assertEqual(result['recorded_status'], 'complete')
        self.assertEqual(result['completion_scope'], 'preparation_only')
        self.assertFalse(result['full_run_complete'])
        self.assertFalse(result['lock_present'])

    def test_live_or_stale_lock_never_claims_liveness_or_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); state = self.state()
            write_json(path / 'run-state.json', state)
            original = (path / 'run-state.json').read_bytes()
            for pid in (os.getpid(), 999999999):
                with self.subTest(pid=pid):
                    write_json(path / '.run.lock', {'pid': pid, 'started_utc': '1900-01-01'})
                    result = execute(parser().parse_args(['status', '--output', str(path)]))
                    self.assertEqual(result['status'], 'active_or_interrupted')
                    self.assertEqual(result['process_liveness'], 'not_checked')
                    self.assertTrue(result['lock_present'])
                    self.assertFalse(result['full_run_complete'])
                    self.assertEqual(result['stages'], state['stages'])
            self.assertEqual((path / 'run-state.json').read_bytes(), original)
            self.assertEqual({p.name for p in path.iterdir()}, {'run-state.json', '.run.lock'})

    def test_full_run_requires_all_six_stages_and_no_lock(self):
        state = self.state(('inventory', 'prepare', 'infer', 'network', 'export', 'validate'))
        result = status_summary(state, False)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['completion_scope'], 'full_run')
        self.assertTrue(result['full_run_complete'])
        locked = status_summary(state, True)
        self.assertEqual(locked['status'], 'active_or_interrupted')
        self.assertFalse(locked['full_run_complete'])
        self.assertEqual(locked['stages'], state['stages'])

    def test_completed_inference_or_network_is_not_complete_run(self):
        state = self.state(('inventory', 'prepare', 'infer'))
        self.assertEqual(status_summary(state, False)['status'], 'inference_complete')
        state['stages']['network'] = {'status': 'complete'}
        state['stages']['validate'] = {'status': 'complete'}
        result = status_summary(state, False)
        self.assertEqual(result['status'], 'networks_complete')
        self.assertEqual(result['completion_scope'], 'networks_without_export')
        self.assertFalse(result['full_run_complete'])

    def test_partial_or_failed_inference_remains_visible_after_export(self):
        for status in ('partial', 'failed', 'interrupted', 'complete_with_failures'):
            with self.subTest(status=status):
                state = self.state(('inventory', 'prepare', 'infer', 'network', 'export', 'validate'))
                state['stages']['infer']['status'] = status
                original = copy.deepcopy(state)
                result = status_summary(state, False)
                self.assertEqual(result['status'], status)
                self.assertFalse(result['full_run_complete'])
                self.assertEqual(result['stages']['infer']['status'], status)
                self.assertEqual(state, original)

    def test_missing_final_inference_receipt_after_reservation_is_incomplete(self):
        state = self.state()
        state['request_registry'] = {'total_reserved': 1}
        result = status_summary(state, False)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['completion_scope'], 'inference_attempts_without_final_receipt')
        self.assertFalse(result['full_run_complete'])

    def test_final_failure_overrides_complete_stage_receipts(self):
        state = self.state(('inventory', 'prepare', 'infer', 'network', 'export', 'validate'), recorded='failed')
        result = status_summary(state, False)
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['full_run_complete'])
        self.assertTrue(all(s['status'] == 'complete' for s in result['stages'].values()))


if __name__ == '__main__':
    unittest.main()
