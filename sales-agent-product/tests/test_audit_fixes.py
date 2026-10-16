import tempfile
import unittest
from pathlib import Path
from sales_agent.config import Config
from sales_agent.store import Store
from sales_agent.leadcontact import LeadContact
from sales_agent.recovery import inspect
from sales_agent.engine import Engine
from sales_agent.native_bridge import complete
from sales_agent.agents.sales import SalesAgent


class AuditFixTests(unittest.TestCase):
    def test_chinese_edit_changes_review_hash_and_requires_both_languages(self):
        from sales_agent.engine import digest
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(Config(data_dir=tmp),provider=object(),leadcontact=object())
            d={'id':'d','status':'pending','to':'person@factory.example','subject':'Question',
               'body':'English','subject_zh':'问题','body_zh':'中文'}
            e.db.put('drafts',d);old=digest(d)
            with self.assertRaises(ValueError):e.edit('d','Question','Changed English')
            changed=e.edit('d','Question','English','问题','修改中文')
            self.assertNotEqual(old,digest(changed))

    def test_successful_cache_does_not_need_online_balance(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Store(tmp+'/live.sqlite3');c=Config(data_dir=tmp)
            balance=[1000]
            def online(path,payload=None):
                if path.endswith('credits'):return {'remainingPoints':balance[0]}
                balance[0]-=10;return {'sources':[]}
            first=LeadContact(c,db,online).email('https://www.linkedin.com/in/person')
            def offline(*args):raise AssertionError('Cache must not access network')
            self.assertEqual(LeadContact(c,db,offline).email('https://www.linkedin.com/in/person'),first)

    def test_response_is_durable_before_balance_settlement(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Store(tmp+'/live.sqlite3');n=[0]
            def transport(path,payload=None):
                if not path.endswith('credits'):return {'sources':[]}
                n[0]+=1
                if n[0]==2:
                    record=db.all('api_calls')[0]
                    self.assertEqual(record['status'],'response_received')
                    self.assertIn('result',record)
                    raise RuntimeError('balance temporarily unavailable')
                return {'remainingPoints':1000}
            LeadContact(Config(),db,transport).email('https://www.linkedin.com/in/person')
            self.assertEqual(db.all('api_calls')[0]['reserved'],10)

    def test_old_day_ambiguous_request_blocks_new_paid_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Store(tmp+'/live.sqlite3')
            db.put('api_calls',{'id':'old','day':'2020-01-01','status':'unknown','reserved':10})
            def balance_only(path,payload=None):
                self.assertTrue(path.endswith('credits'));return {'remainingPoints':1000}
            with self.assertRaises(ValueError):
                LeadContact(Config(),db,balance_only).email('https://www.linkedin.com/in/new')

    def test_recovery_selects_latest_and_excludes_reported_sent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'live.sqlite3';db=Store(path)
            for ident,company,outcome,time in [('old','A','needs_verification','2026-01-01'),('new','A','draft_ready','2026-10-16'),('b','B','needs_contact','2026-10-16')]:
                db.put('settings',{'id':'research_outcome:'+ident,'company':company,'outcome':outcome,'reviewed_at':time,'reason':'test'})
            db.put('contacts',{'id':'sent','company':'B','status':'reported_sent'})
            state=inspect(path)
            self.assertEqual(state['unresolved_reviews'],[])
            self.assertEqual(state['ready_personal_bilingual_drafts'],0)

    def test_bridge_rejects_missing_translation_before_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            class LC:
                def email(self,url):raise AssertionError('Must not spend without bilingual copy')
            e=Engine(Config(data_dir=tmp),provider=object(),leadcontact=LC())
            with self.assertRaisesRegex(ValueError,'Chinese'):
                complete(e,{}, {}, [],set(),{'subject':'Question','body':'English only'},True)

    def test_standalone_sales_keeps_both_languages(self):
        class P:
            def extract(self,prompt,schema):
                self_schema=schema['properties']
                assert 'subject_zh' in self_schema
                return {'subject':'Question','body':'English question','subject_zh':'问题','body_zh':'中文问题'}
        d=SalesAgent(P(),Config()).run({'id':'a','email':'person@factory.example','validated':True,'status':'pending_review'})
        self.assertEqual(d['subject_zh'],'问题')
        self.assertIn('中文问题',d['body_zh'])
