import asyncio
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from sales_agent.config import Config
from sales_agent.connector import Connector
from sales_agent.engine import Engine


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.calls = []
        class LC:
            def search(inner, payload):
                self.calls.append(payload)
                return {'employees': [], 'nextPageToken': 'returned-token'}
            def email(inner, url):
                self.fail('No paid email allowed in validation rejection tests')
        self.e = Engine(Config(mode='live', data_dir=self.tmp.name, research_backend='native'),
                        provider=object(), leadcontact=LC())
        self.s = Connector(self.e, paid_enabled=True)
        self.payload = {'location': ['France'], 'currentTitlesOnly': True, 'jobTitle': ['Quality Manager']}
        self.review = {'history_reviewed': True, 'business_query_reviewed': True, 'reason': 'Reviewed task'}
        self.day = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
        self.e.db.put('settings', {'id': 'connector_master_sync', 'day': self.day,
                                  'revision': 'test-only', 'history_complete': True})

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_closed_and_missing_master(self):
        with self.assertRaisesRegex(ValueError, 'disabled'):
            Connector(self.e).ready(10)
        self.e.db.put('settings', {'id': 'connector_master_sync', 'day': '2000-01-01'})
        with self.assertRaisesRegex(ValueError, 'sync required'):
            self.s.ready(10)

    def test_unknown_request_blocks_new_spend(self):
        self.e.db.put('api_calls', {'id': 'old', 'day': '2020-01-01', 'status': 'unknown', 'reserved': 10})
        with self.assertRaisesRegex(ValueError, 'Unresolved'):
            self.s.ready(10)

    def test_protect_email_budget(self):
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.s.plan_search(self.payload, self.review, 110)
        self.assertEqual(self.calls, [])

    def test_replay_same_plan_makes_one_search(self):
        p = self.s.plan_search(self.payload, self.review, 20)
        self.assertFalse(self.s.search(p['plan_id'])['cached'])
        self.assertTrue(self.s.search(p['plan_id'])['cached'])
        self.assertEqual(len(self.calls), 1)

    def test_ambiguous_plan_does_not_retry(self):
        p = self.s.plan_search(self.payload, self.review, 10)
        record = self.e.db.get('settings', p['plan_id'])
        record['attempted'] = 'unknown'
        self.e.db.put('settings', record)
        with self.assertRaisesRegex(ValueError, 'uncertain'):
            self.s.search(p['plan_id'])
        self.assertEqual(self.calls, [])

    def test_unsupported_enum_and_fabricated_pagination(self):
        for extra in ({'industry': ['invented']}, {'nextPageToken': 'invented'}):
            with self.assertRaises(ValueError):
                self.s.plan_search(dict(self.payload, **extra), self.review, 10)

    def test_old_successful_search_is_reused_without_paid_call(self):
        self.e.db.put('api_calls', {'id': 'old', 'day': '2020-01-01', 'kind': 'search',
                                  'status': 'completed', 'payload': self.payload,
                                  'cost': 5, 'result': {'employees': []}})
        p = self.s.plan_search(self.payload, self.review, 10)
        self.assertTrue(self.s.search(p['plan_id'])['cached'])
        self.assertEqual(self.calls, [])

    def test_save_research_does_not_claim_library_sync(self):
        r = self.s.save_research({'company': 'Example', 'disposition': 'needs_contact',
                                 'reason': 'Reviewed', 'sources': ['https://factory.example/team'],
                                 'next_action': 'Verify current person'})
        self.assertFalse(r['canonical_master_synced'])

    def test_email_rejects_weak_match_before_lookup(self):
        with self.assertRaisesRegex(ValueError, 'Highly matched'):
            self.s.prepare_email('stable-request-0001', {}, {}, [], [], {}, {})
        self.assertEqual(self.calls, [])


class MCPTests(unittest.TestCase):
    def test_no_scope_blocks_handler(self):
        from sales_agent.mcp_server import require_scope
        with self.assertRaises(PermissionError):
            require_scope('sales:paid')

    def test_sdk_registers_only_six_tools_and_paid_annotations(self):
        from sales_agent.mcp_server import build_server
        class V:
            async def verify_token(self, token): return None
        m = build_server(object(), 'https://auth.example', 'https://connector.example/mcp', V())
        tools = asyncio.run(m.list_tools())
        self.assertEqual(len(tools), 6)
        self.assertFalse(any('send' in t.name for t in tools))
        paid = next(t for t in tools if t.name == 'execute_people_search')
        self.assertFalse(paid.annotations.readOnlyHint)
        self.assertTrue(paid.annotations.openWorldHint)

    def test_transport_rejects_unauthenticated_request(self):
        import httpx
        from sales_agent.mcp_server import build_server
        class V:
            async def verify_token(self, token): return None
        m = build_server(object(), 'https://auth.example', 'https://connector.example/mcp', V())
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=m.streamable_http_app()),
                                         base_url='https://connector.example') as client:
                r = await client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
                self.assertEqual(r.status_code, 401)
                self.assertIn('resource_metadata', r.headers['www-authenticate'])
        asyncio.run(check())
