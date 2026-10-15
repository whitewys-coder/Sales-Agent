import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from sales_agent.store import Store
from sales_agent.research_queue import checkpoint
from sales_agent.recovery import inspect, backup


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'live.sqlite3'
        self.db = Store(self.path)
        self.db.put('runs', {'id': 'run', 'status': 'awaiting_native_research'})
        self.db.put('settings', {'id': 'native_research_queue', 'run_id': 'run',
                                'value': [{'company': 'Factory'}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_failed_run_update_rolls_back_outcome_and_queue(self):
        with self.db.connect() as con:
            con.execute("CREATE TRIGGER fail_run BEFORE INSERT ON runs BEGIN SELECT RAISE(ABORT,'crash'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            checkpoint(self.db, 'Factory', 'observe', 'Reason', ['https://example.test'])
        self.assertEqual(len(self.db.get('settings', 'native_research_queue')['value']), 1)
        self.assertFalse(any(x['id'].startswith('research_outcome:') for x in self.db.all('settings')))

    def test_backup_and_restart_preserve_pending_and_budget(self):
        self.db.put('api_calls', {'id': 'uncertain', 'day': '2026-10-15',
                                 'status': 'unknown', 'reserved': 100})
        copy = Path(self.tmp.name) / 'checkpoint.sqlite3'
        backup(self.path, copy)
        state = inspect(copy)
        self.assertEqual(state['pending_companies'], ['Factory'])
        self.assertEqual(state['ambiguous_paid_requests'], ['uncertain'])
        self.assertFalse(state['paid_retry_allowed'])
        self.assertEqual(copy.stat().st_mode & 0o777, 0o600)

    def test_review_is_idempotent_and_not_business_completion(self):
        self.assertTrue(checkpoint(self.db, 'Factory', 'needs_verification', 'Role unclear', ['https://example.test']))
        self.assertFalse(checkpoint(self.db, 'Factory', 'needs_verification', 'Same', ['https://example.test']))
        state = inspect(self.path)
        self.assertEqual(state['pending_companies'], [])
        self.assertEqual(len(state['unresolved_reviews']), 1)
        self.assertNotEqual(state['writeback_status'], 'completed')
