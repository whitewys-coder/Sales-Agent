import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).parent/'runtime'))
import tempfile,unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from sales_agent.config import Config
from sales_agent.store import Store
from sales_agent.leadcontact import LeadContact
from sales_agent.rules import verify_current,person_key
from sales_agent.agents.scoring import ScoringAgent
from sales_agent.engine import Engine

class V33Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.c=Config(mode='live',data_dir=self.tmp.name,api_key='test',model='test',leadcontact_token='test')
  self.db=Store(self.tmp.name+'/live.sqlite3')
 def tearDown(self):self.tmp.cleanup()
 def test_conflicting_api_can_be_resolved_by_official_evidence(self):
  p={'fullName':'Example Person','companyName':'EXAMPLE WORKS','experience':[{'companyName':'EXAMPLE WORKS','isCurrent':False}]}
  e={'name':p['fullName'],'company':p['companyName'],'title':'Responsable Qualité','current':True,'kind':'official_contact','url':'https://example-works.test/team','checked_date':datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()}
  self.assertFalse(verify_current(p,[],set())['verified'])
  result=verify_current(p,[e],{e['url']});self.assertTrue(result['verified']);self.assertTrue(result['api_conflict'])
  self.assertFalse(verify_current(p,[dict(e,current=False),e],{e['url']})['verified'])
 def test_unretrieved_employment_and_similar_name_rejected(self):
  p={'fullName':'Same Name','companyName':'Factory'}
  e={'name':'Same Name','company':'Other Factory','title':'CTO','current':True,'kind':'official_contact','url':'https://x.example/team','checked_date':datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()}
  self.assertFalse(verify_current(p,[e],{e['url']})['verified'])
  self.assertEqual(person_key('https://evil-linkedin.com/in/person'),'')
  e.update(company='Factory')
  self.assertFalse(verify_current(p,[e],{e['url']},company_domain='factory.example')['verified'])
 def test_budget_timeout_reservation_blocks_retry_and_restart(self):
  calls=[]
  def transport(path,payload=None):
   if path.endswith('credits'):return {'remainingPoints':1000}
   calls.append(path);raise TimeoutError()
  lc=LeadContact(self.c,self.db,transport)
  query={'location':['France']}
  with self.assertRaises(TimeoutError):lc.search(query)
  with self.assertRaises(ValueError):LeadContact(self.c,self.db,transport).search(query)
  with self.assertRaises(ValueError):lc.search({'location':['Germany']})
  self.assertEqual(len(calls),1)
 def test_budget_hard_limit_and_cached_response(self):
  calls=[];balance=[1000]
  def transport(path,payload=None):
   if path.endswith('credits'):return {'remainingPoints':balance[0]}
   calls.append(path);balance[0]-=100 if 'advanced' in path else 10
   return {'employees':[]} if 'advanced' in path else {'sources':[]}
  lc=LeadContact(self.c,self.db,transport);q={'location':['France']}
  lc.search(q);lc.search(q)
  for i in range(10):lc.email('https://www.linkedin.com/in/p'+str(i))
  with self.assertRaises(ValueError):lc.email('https://www.linkedin.com/in/extra')
  self.assertEqual(len(calls),11)
 def test_score_85_and_exploration_and_unknown_evidence(self):
  u='https://factory.example/product';a={'research_validated':True,'in_scope':True,'technical_fit':True,'fit_reason':'A concrete assembly step',
   'sources':[{'url':u,'kind':'scene'}],'contact_verified':True,'email':'x@factory.example','email_verified':True,'email_valid':True,'email_personal':False,
   'email_domain_match':True,'email_business_use':True,'employees':120,'employees_verified':True,'recent_trigger_verified':True,'trigger_date':datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()}
  def part(v):return {'points':v,'reason':'Evidence','urls':[u]}
  a['score_evidence']={k:[part(v) for v in vs] for k,vs in {'trigger':[20],'technical_fit':[10,10,5],'decision_maker':[4,4,3,2,2],'public_email':[3,3,2,2],'strategic':[2,2,1]}.items()}
  s=ScoringAgent().run(a);self.assertEqual(s['score'],95);self.assertEqual(s['channel'],'priority')
  a['score_evidence']['trigger'][0]['points']=10;s=ScoringAgent().run(a);self.assertEqual(s['score'],85);self.assertEqual(s['channel'],'priority')
  a['recent_trigger_verified']=False;s=ScoringAgent().run(a);self.assertEqual(s['score'],60);self.assertEqual(s['status'],'pending_review');self.assertEqual(s['channel'],'exploratory')
  a['email_valid']=False;self.assertFalse(ScoringAgent().run(a)['validated'])
 def test_native_backend_queues_research_without_openai_key(self):
  self.c.api_key='';self.c.model='';self.c.research_backend='native'
  class LC:
   def search(self,p):return {'employees':[{'fullName':'Example Person','companyName':'Factory'}]}
  e=Engine(self.c,provider=object(),leadcontact=LC());e.db.put('settings',{'id':'search_payload','value':{'location':['France']}})
  r=e.run();self.assertEqual(r['status'],'awaiting_native_research');self.assertTrue(e.state()['configured']);self.assertEqual(len(e.db.get('settings','native_research_queue')['value']),1)
 def test_native_bridge_real_stages_without_model_api(self):
  from sales_agent.native_bridge import complete
  self.c.research_backend='native';self.c.api_key='';self.c.model=''
  class LC:
   def email(self,url):return {'sources':[{'email':'person@factory.example','valid':True,'personal':False}]}
  e=Engine(self.c,provider=object(),leadcontact=LC());u='https://factory.example/team'
  a={'company':'Factory','domain':'factory.example','group_domain':'factory.example','country':'France','pool':'direct','company_role':'manufacturer','in_scope':True,'technical_fit':True,'fit_reason':'A specific assembly verification question','sources':[{'url':u,'kind':'product','claim':'Assembly manufacturing'}],'score_evidence':{}}
  p={'fullName':'Example Person','companyName':'Factory','linkedinUrl':'https://www.linkedin.com/in/example-person'}
  proof=[{'name':'Example Person','company':'Factory','title':'Quality Manager','current':True,'kind':'official_contact','url':u,'checked_date':datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()}]
  with self.assertRaises(ValueError):complete(e,a,p,proof,{u},{'subject':'Task','body':'Question'},False)
  result=complete(e,a,p,proof,{u},{'subject':'Assembly check','body':'A specific verification question.'},True)
  self.assertEqual(result['status'],'pending');self.assertEqual(len(e.db.all('drafts')),1)
  with self.assertRaises(ValueError):e.send(result['draft_id'])
  with self.assertRaises(ValueError):complete(e,a,p,proof,{u},{'subject':'Duplicate','body':'No'},True)
 def test_complete_live_orchestration_with_fake_network(self):
  from sales_agent.agents.validation import evidence_gate
  e=Engine(self.c,provider=object(),leadcontact=object())
  e.db.put('settings',{'id':'search_payload','value':{'location':['France']}})
  class LC:
   def search(self,p):return {'employees':[{'fullName':'Person','companyName':'Factory','linkedinUrl':'https://www.linkedin.com/in/p'}]*2}
  e.lc=LC()
  class Validation:
   name='Validation'
   def run(self,c,scope):return {'company':'Factory','discovered_company':'Factory','domain':'factory.example','group_domain':'factory.example','research_validated':True,'in_scope':True,'technical_fit':True,'fit_reason':'Assembly checks','sources':[]}
  class Enrich:
   name='Enrichment'
   def run(self,a):a.update(contact='Person',contact_verified=True,email='p@factory.example',email_verified=True,email_valid=True,email_personal=False,email_domain_match=True,email_business_use=True);return a
  class Sales:
   name='Sales'
   def run(self,a):return {'id':'draft','account_id':a['id'],'to':a['email'],'subject':'Assembly checks','body':'Evidence-based question','status':'pending','demo':False}
  e.validation=Validation();e.enrichment=Enrich();e.sales=Sales()
  r=e.run();self.assertEqual(r['status'],'completed');self.assertEqual(r['discovered_companies'],1);self.assertEqual(r['new_drafts'],1)
  self.assertEqual(e.run()['new_drafts'],0)
  with self.assertRaises(ValueError):e.send('draft')

if __name__=='__main__':unittest.main(verbosity=2)
