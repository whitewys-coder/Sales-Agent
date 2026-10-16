"""V3.3 deterministic gates; external assertions never imply delivery or demand."""
import re
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit, unquote

EU = {'Germany','France','Italy','Spain','Netherlands','Belgium','Switzerland','Austria','Czechia','Hungary'}
SEA = {'Singapore','Malaysia','Thailand','Vietnam','Indonesia','Philippines'}
CAPS = {'trigger':25,'technical_fit':25,'freshness':15,'decision_maker':15,'public_email':10,'size':5,'strategic':5}
SUBCAPS = {'technical_fit': [10,10,5], 'decision_maker':[4,4,3,2,2], 'public_email':[3,3,2,2], 'strategic':[2,2,1]}
FREEMAIL = {'gmail.com','qq.com','outlook.com','hotmail.com','yahoo.com','163.com','foxmail.com','web.de'}

def norm(s):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', s or '') if not unicodedata.combining(c)).casefold().split())

def person_key(url):
    p=urlsplit(url)
    return unquote(p.path).rstrip('/').casefold() if ((p.hostname or '')=='linkedin.com' or (p.hostname or '').endswith('.linkedin.com')) and p.path.startswith('/in/') else ''

def verify_current(person, evidence, retrieved, today=None, company_domain=None):
    """Require separate evidence; retain API conflicts instead of rejecting automatically."""
    today=today or datetime.now(ZoneInfo('Asia/Shanghai')).date()
    def authentic(x):
        host=(urlsplit(x.get('url','')).hostname or '').lower().removeprefix('www.')
        if x.get('kind')=='personal_profile':return person_key(x.get('url',''))==person_key(person.get('linkedinUrl','')) and bool(person_key(x.get('url','')))
        return not company_domain or host==company_domain.lower().removeprefix('www.')
    matches=[x for x in evidence if x.get('url') in retrieved and authentic(x) and x.get('current') is True
             and norm(x.get('name'))==norm(person.get('fullName'))
             and norm(x.get('company'))==norm(person.get('companyName'))
             and x.get('title') and x.get('kind') in ('official_contact','official_appointment','personal_profile')
             and x.get('checked_date')==today.isoformat()]
    api_flags=[x.get('isCurrent') for x in person.get('experience',[]) if norm(x.get('companyName'))==norm(person.get('companyName'))]
    # A past role at the same employer is normal when another role is current.
    conflicts=any(x is False for x in api_flags) and not any(x is True for x in api_flags)
    explicit_exit=any(x.get('url') in retrieved and authentic(x) and x.get('current') is False
                      and norm(x.get('name'))==norm(person.get('fullName'))
                      and norm(x.get('company'))==norm(person.get('companyName')) for x in evidence)
    return {'verified':bool(matches) and not explicit_exit, 'api_conflict':conflicts,
            'evidence':matches, 'checked_at':today.isoformat(),
            'status':'conflict' if explicit_exit and matches else 'verified' if matches and not explicit_exit else 'unverified'}

def research_eligible(a):
    return bool(a.get('research_validated') and a.get('in_scope') and not a.get('excluded')
                and a.get('technical_fit') and a.get('fit_reason') and a.get('status') not in ('sent','replied','rejected','bounced','reported_sent','reported_forwarded'))

def email_eligible(a):
    e=a.get('email','').strip().lower()
    return bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',e) and e.split('@')[-1] not in FREEMAIL
                and a.get('email_verified') and a.get('email_valid') is True and a.get('email_personal') is False
                and a.get('email_domain_match') is True and a.get('email_business_use') is True)
