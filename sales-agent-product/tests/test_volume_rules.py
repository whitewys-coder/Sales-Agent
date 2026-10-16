import tempfile
import unittest
from sales_agent.config import Config
from sales_agent.store import Store
from sales_agent.leadcontact import LeadContact
from sales_agent.rules import named_corporate_email, email_eligible


class VolumeRulesTests(unittest.TestCase):
    def test_named_corporate_excludes_shared_and_free_addresses(self):
        for email in ('info@factory.example','commercial@factory.example','courrier.france@factory.example','sales-eu@factory.example','person@gmail.com'):
            self.assertFalse(named_corporate_email(email))
        self.assertTrue(named_corporate_email('j.smith@factory.example'))
        a=dict(email='j.smith@factory.example',email_verified=True,email_valid=True,
               email_personal=False,email_domain_match=True,email_business_use=True)
        self.assertFalse(email_eligible(a))
        a['contact_verified']=True
        self.assertTrue(email_eligible(a))

    def test_two_real_pagination_tokens_share_budget_and_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=Config(mode='live',data_dir=tmp,leadcontact_token='test')
            db=Store(tmp+'/live.sqlite3');balance=[1000];calls=[]
            def transport(path,payload=None):
                if path.endswith('credits'):return {'remainingPoints':balance[0]}
                calls.append(payload);balance[0]-=100
                return {'employees':[{'companyName':'Factory'}]*20}
            lc=LeadContact(c,db,transport)
            first={'location':['France']};second={'location':['France'],'nextPageToken':'server-issued-token'}
            lc.search(first);lc.search(second);lc.search(second)
            self.assertEqual(len(calls),2)
            with self.assertRaises(ValueError):lc.email('https://www.linkedin.com/in/p')

    def test_flexible_processing_limit_default(self):
        self.assertEqual(Config().max_accounts,0)
