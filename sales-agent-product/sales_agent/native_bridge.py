"""Authenticated/operator bridge for research and copy produced in ChatGPT Work.

The caller must have actually retrieved and reviewed the supplied source URLs.
This is an explicit reviewed-data boundary, not an autonomous web researcher.
"""
from .agents.validation import evidence_gate
from .agents.scoring import ScoringAgent
from .rules import verify_current,research_eligible,email_eligible,norm
from .store import now,uid

def complete(engine, account, person, employment_evidence, retrieved_urls, copy, evidence_reviewed=False):
    if evidence_reviewed is not True:raise ValueError('Explicit evidence review required')
    a=evidence_gate(dict(account),set(retrieved_urls))
    a.update(id=account.get('id') or uid(),updated_at=now(),demo=False)
    if not research_eligible(a):raise ValueError('Company research gate failed')
    keys={a['domain'],a['group_domain']}
    if any(c.get('domain') in keys or norm(c.get('company'))==norm(a['company']) for c in engine.db.all('contacts')):
        raise ValueError('Historical contact/group suppression')
    existing=next((x for x in engine.db.all('accounts') if x.get('domain')==a['domain']),None)
    if existing and existing.get('status')=='needs_contact':a['id']=existing['id']
    elif engine.known(a):raise ValueError('Known account/group; do not repeat first contact')
    v=verify_current(person,employment_evidence,set(retrieved_urls),company_domain=a['domain'])
    if not v['verified']:raise ValueError('Current employment requires second verification')
    a.update(contact=person['fullName'],contact_title=v['evidence'][0]['title'],contact_verified=True,
             linkedin_url=person['linkedinUrl'],current_verification=v)
    a['research_backend']='native_reviewed'
    a['score_evidence']=account.get('score_evidence',{})
    engine.db.put('accounts',dict(a,status='needs_contact'))
    # Use the SAME budget ledger and cached paid client as standalone execution.
    result=engine.lc.email(person['linkedinUrl'])
    chosen=next((s for s in result.get('sources',[]) if s.get('valid') is True and s.get('personal') is False and s.get('email','').split('@')[-1].lower() in (a['domain'],a['group_domain'])),None)
    if not chosen:
        a.update(status='needs_contact',enrichment_issues=['No suitable business email']);engine.db.put('accounts',a)
        return {'status':'needs_contact','account_id':a['id']}
    a.update(email=chosen['email'].lower(),email_verified=True,email_valid=True,email_personal=False,email_domain_match=True,email_business_use=True,email_checked_at=now())
    u='https://api.leadcontact.ai/api/rest/email/query'
    a['sources'].append({'url':u,'kind':'email_api','claim':a['email']+' valid=true personal=false','publisher':'LeadContact'})
    a['score_evidence']['public_email']=[{'points':p,'reason':reason,'urls':[u]} for p,reason in [(2,'Returned for exact verified profile and domain'),(3,'API valid now'),(2,'Relevant work contact'),(2,'Exact profile match')]]
    ScoringAgent().run(a);engine.db.put('accounts',a)
    if not a['validated']:return {'status':'needs_contact','account_id':a['id']}
    if any(d.get('account_id')==a['id'] for d in engine.db.all('drafts')):raise ValueError('Draft already exists')
    subject,body=copy.get('subject','').strip(),copy.get('body','').strip()
    if not subject or not body or '\n' in subject or '\r' in subject:raise ValueError('Subject and body required')
    draft={'id':uid(),'account_id':a['id'],'to':a['email'],'subject':subject,'body':body+'\n\nBest regards,\nAlen Wang\nXeroptix\nAlenWang@xeroptix.com\nhttps://xeroptix.com',
           'status':'pending','created_at':now(),'approved_hash':'','demo':False,'research_backend':'native_reviewed'}
    engine.db.put('drafts',draft)
    engine.db.event('Native Research Bridge','completed','Reviewed research, current-employment check, budgeted email lookup and draft saved; manual sending only')
    return {'status':'pending','account_id':a['id'],'draft_id':draft['id'],'score':a['score'],'channel':a['channel'],'to':a['email']}
