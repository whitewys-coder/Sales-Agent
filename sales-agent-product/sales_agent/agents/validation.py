import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from ..provider import obj,array,TEXT,BOOL,NUMBER
from ..rules import EU,SEA

SOURCE=obj({'url':TEXT,'kind':TEXT,'claim':TEXT,'publisher':TEXT})
PART=obj({'points':NUMBER,'reason':TEXT,'urls':array(TEXT)})
SCORES=obj({k:array(PART) for k in ('trigger','technical_fit','decision_maker','public_email','strategic')})
SCHEMA=obj({**{k:TEXT for k in ('company','domain','group_domain','country','trigger','trigger_date','contact','email','why_now','fit_reason','exclusion_reason','pool','company_role')},
 'employees':NUMBER,'in_scope':BOOL,'excluded':BOOL,'independent_sources':BOOL,'technical_fit':BOOL,'strategic':BOOL,'contact_verified':BOOL,'email_verified':BOOL,
 'recent_trigger_verified':BOOL,'sources':array(SOURCE),'score_evidence':SCORES})

def domain(value):
    parsed=urlparse(value if '://' in value else 'https://'+value)
    host=(parsed.hostname or '').lower().removeprefix('www.').rstrip('.')
    return host if re.fullmatch(r'[a-z0-9.-]+\.[a-z]{2,}',host) else ''

def address(value):return bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value))

def evidence_gate(a,retrieved_urls,today=None):
    today=today or datetime.now(ZoneInfo('Asia/Shanghai')).date();problems=[]
    a['domain']=domain(a.get('domain',''));a['group_domain']=domain(a.get('group_domain','')) or a['domain']
    sources=[s for s in a.get('sources',[]) if s.get('url') in retrieved_urls and urlparse(s['url']).scheme=='https']
    official=[s for s in sources if domain(s['url']) in (a['domain'],a['group_domain']) and s.get('kind') in ('company','product','scene','official_trigger')]
    if not a['domain'] or not official:problems.append('official company/product/scene evidence required')
    if a['group_domain']!=a['domain'] and not any(s.get('kind')=='group' for s in sources):problems.append('group evidence missing')
    pool=a.get('pool','direct');country=a.get('country','')
    scope_ok=(pool=='direct' and (country in EU or country=='China' and any(s.get('kind')=='outbound_market' for s in sources))) or (pool=='europe_channel' and country in EU) or (pool=='sea_channel' and country in SEA)
    if a.get('company_role') in ('institution','competitor') or (pool=='direct' and a.get('company_role') not in ('OEM','manufacturer')):problems.append('company role not direct/OEM or partner eligible')
    if not scope_ok or not a.get('in_scope') or a.get('excluded') or not a.get('technical_fit') or not a.get('fit_reason'):problems.append('scope/role/task gate failed')
    if not any(s.get('kind')=='employees' for s in sources):a['employees']=0
    a['employees_verified']=bool(a.get('employees') and any(s.get('kind')=='employees' for s in sources))
    official_trigger=any(s.get('kind')=='official_trigger' for s in official)
    try:recent=0<=(today-date.fromisoformat(a.get('trigger_date',''))).days<=90
    except ValueError:recent=False
    a['recent_trigger_verified']=bool(a.get('recent_trigger_verified') and official_trigger and recent)
    # Contact/email are NOT company research admission requirements.
    a['contact_verified']=False;a['email_verified']=False
    a['research_validated']=not problems;a['validated']=False
    a['validation_issues']=problems;a['sources']=sources;a['evidence_review_required']=True
    return a

class ValidationAgent:
    name='Validation Agent'
    def __init__(self,provider):self.provider=provider
    def run(self,candidate,scope):
        report,urls=self.provider.research('Research this LeadContact-discovered COMPANY, not a new unrelated company: '+json.dumps(candidate)+
          '. Scope: '+scope+'. Verify official identity, parent/group, product/process, fit and existing AI. '
          'Recent trigger and public budget are optional; no unmet-need claim without evidence. Company roles: OEM, manufacturer, channel, institution, competitor. '
          'Exclude same-product vision and embedded AI hardware vendors. European integrators belong europe_channel, SEA engineering partners sea_channel, direct customers direct. '
          'China-outbound must evidence Europe/USA/South America and label source outbound_market; exclude Africa/SEA direct. '
          'Use source kinds company/product/scene/official_trigger/group/employees/outbound_market. Do not request or invent an email. '
          'Score evidence arrays have fixed order/caps: trigger[25]; technical_fit[scene10,function10,feasibility5]; decision_maker[identity4,authority4,relevance3,path2,freshness2]; '
          'public_email[ownership3,validity3,purpose2,matching2]; strategic[business2,replication2,market1]. Each part needs actual retrieved URL and reason; unknown=0. '
          'No contact/email evidence yet means zero for those items. First event publication date, not repost/crawl date. Existing suppliers are not automatic exclusion.')
        a=self.provider.extract('Extract only facts in this research; empty unknown fields. Contact/email are empty until later enrichment.\n'+report,SCHEMA)
        a['validation_report']=report;a['leadcontact_people']=candidate.get('people',[])
        a['discovered_company']=candidate['company']
        return evidence_gate(a,set(urls))
