"""Import user-provided history conservatively; never turn a draft into a sent event."""
import hashlib
from .rules import norm,person_key
from .agents.validation import domain
from .store import now

def import_rows(db,rows,source):
    count=0
    for r in rows:
        status=r.get('status','').lower()
        if status not in ('sent','reported_sent','reported_forwarded','forwarded','rejected','bounced','excluded','handed_off'):continue
        company=r.get('companyName',r.get('company','')).strip();email=r.get('email','').strip().lower()
        if not company and not email:continue
        ident=hashlib.sha256((source+'|'+company+'|'+email+'|'+r.get('linkedinUrl','')).encode()).hexdigest()
        host=domain(r.get('companyWebsite','')) or (email.split('@')[-1] if '@' in email else '')
        db.put('contacts',{'id':email or ident,'company':company,'domain':host,'linkedin_key':person_key(r.get('linkedinUrl','')),
            'status':'reported_sent' if status=='sent' else 'reported_forwarded' if status=='forwarded' else status,
            'source':source,'source_date':r.get('date',''),'recorded_at':now(),
            'note':'Source-recorded status; not independently verified sending/delivery'})
        count+=1
    return count
