import json
from datetime import datetime
from zoneinfo import ZoneInfo
from ..provider import obj,array,TEXT,BOOL
from ..rules import verify_current, email_eligible, norm, research_eligible
from .validation import SOURCE,SCORES

EVIDENCE=obj({'name':TEXT,'company':TEXT,'title':TEXT,'current':BOOL,'kind':TEXT,'url':TEXT,'checked_date':TEXT})
SCHEMA=obj({'evidence':array(EVIDENCE),'sources':array(SOURCE),'score_evidence':SCORES})
class EnrichmentAgent:
    name='Contact & Email Agent'
    def __init__(self,provider,lc):self.p,self.lc=provider,lc
    def run(self,a):
        if not research_eligible(a):return a
        a['enrichment_issues']=[]
        for person in a.get('leadcontact_people',[]):
            if norm(person.get('companyName'))!=norm(a.get('discovered_company',a['company'])):continue
            report,urls=self.p.research('Verify CURRENT employment and responsibilities of this exact person: '+json.dumps(person)+
               '. Company official domain '+a['domain']+'. API isCurrent may be stale. Open official current team/appointment page or original personal LinkedIn profile; '
               'a list, snippet or copied API result is not independent verification. Record exact name/company/title, source kind official_contact/official_appointment/personal_profile, '
               'checked_date '+datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()+'. Explicit departure or conflicting current employer must be reported. No new contact names invented. '
               'Return evidence-based decision_maker component scores [identity4,authority4,relevance3,path2,freshness2].')
            r=self.p.extract('Extract checked employment evidence, sources and scores, zero/empty for unknown.\n'+report,SCHEMA)
            current=verify_current(person,r['evidence'],set(urls),company_domain=a['domain'])
            a['current_verification']=current
            if not current['verified']:
                a['enrichment_issues'].append('current employment unverified: '+person['fullName']);continue
            a.update(contact=person['fullName'],contact_title=current['evidence'][0]['title'],contact_verified=True,linkedin_url=person['linkedinUrl'])
            a['sources'] += [s for s in r['sources'] if s['url'] in urls]
            a.setdefault('score_evidence',{})['decision_maker']=r['score_evidence']['decision_maker']
            response=self.lc.email(person['linkedinUrl'])
            for source in response.get('sources',[]):
                email=source.get('email','').lower();host=email.split('@')[-1]
                match=host in (a['domain'],a['group_domain'])
                a.update(email=email,email_valid=source.get('valid'),email_personal=source.get('personal'),email_domain_match=match,
                    email_business_use=True,email_verified=bool(match and source.get('valid') is True and source.get('personal') is False),email_checked_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat())
                if email_eligible(a):
                    url='https://api.leadcontact.ai/api/rest/email/query'
                    a['sources'].append({'url':url,'kind':'email_api','claim':email+' valid=true personal=false; not proof of delivery','publisher':'LeadContact'})
                    a['score_evidence']['public_email']=[{'points':v,'reason':reason,'urls':[url]} for v,reason in [(2,'API plus company/group domain match'),(3,'Current API valid result'),(2,'Work address for verified business role'),(2,'Address returned for exact profile')]]
                    return a
            a['enrichment_issues'].append('No usable corporate mailbox; do not send')
        return a
