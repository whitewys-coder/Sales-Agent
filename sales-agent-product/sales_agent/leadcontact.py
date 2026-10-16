"""Serial, crash-safe daily reservations. Never retry ambiguous paid HTTP requests."""
import json
import hashlib
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from .store import now, uid

class LeadContact:
    def __init__(self, config, store, transport=None):
        self.c,self.db,self.transport=config,store,transport or self.http

    def http(self, path, payload=None):
        if not self.c.leadcontact_token: raise ValueError('LEADCONTACT_TOKEN missing')
        req=urllib.request.Request('https://api.leadcontact.ai'+path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Authorization':'Bearer '+self.c.leadcontact_token,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=40) as r: result=json.load(r)
        except Exception as exc:
            raise RuntimeError('LeadContact request failed: '+type(exc).__name__+'; no automatic retry') from None
        if result.get('code')!=200: raise RuntimeError('LeadContact business error '+str(result.get('code')))
        return result.get('data',{})

    def balance(self):
        value=self.transport('/api/rest/credits').get('remainingPoints')
        if type(value) is not int or value<0: raise ValueError('Balance unreadable; paid calls blocked')
        return value

    def paid(self, kind, payload, reserve):
        day=datetime.now(ZoneInfo(self.c.timezone)).date().isoformat()
        key=hashlib.sha256(json.dumps([day,kind,payload],sort_keys=True).encode()).hexdigest()
        cached=self.db.get('api_calls',key)
        if cached and cached.get('status')=='completed':
            return cached['result']
        if cached:
            raise ValueError('Request already attempted/uncertain; reconcile before retry')
        before=self.balance()
        record={'id':key,'day':day,'kind':kind,'payload':payload,'reserved':reserve,'status':'reserved','created_at':now()}
        # A transaction shared by all processes using this DB reserves before the HTTP request.
        with self.db.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            rows=[json.loads(x[0]) for x in con.execute('SELECT body FROM api_calls')]
            old=next((x for x in rows if x['id']==key),None)
            if old:
                if old['status']=='completed': return old['result']
                raise ValueError('Request already attempted/uncertain; reconcile before retry')
            daily=[x for x in rows if x['day']==day]
            if any(x.get('status')!='completed' for x in rows):
                raise ValueError('Unresolved paid request; reconcile before further paid work')
            used=sum(x.get('cost',x['reserved']) for x in daily)
            if used+reserve>self.c.credit_hard_limit or before<reserve: raise ValueError('Daily credit hard limit')
            con.execute('INSERT INTO api_calls VALUES (?,?)',(key,json.dumps(record)))
        try:
            path={'search':'/api/rest/employess/query/advanced','email':'/api/rest/email/query'}[kind]
            result=self.transport(path,payload)
            # Persist response even if subsequent free balance read fails. Never repeat paid call.
            record.update(result=result,status='response_received',response_received_at=now())
            self.db.put('api_calls',record)
            try:
                after=self.balance();delta=before-after
                record.update(balance_before=before,balance_after=after)
                if delta>=0: record['cost']=max(delta,reserve) if delta>reserve else delta
                else: record['billing_status']='unknown; balance increased'
            except Exception:record['billing_status']='unknown; reservation retained'
            record.update(status='completed',finished_at=now())
            self.db.put('api_calls',record)
            return result
        except Exception:
            record.update(status='unknown',finished_at=now());self.db.put('api_calls',record)
            raise

    def search(self, payload):
        if len(payload.get('location',[]))!=1:
            raise ValueError('Single country search required')
        # 5 credits per returned person, up to 20 people per known page.
        # Reserve the worst case until supported smaller-page parameters are verified.
        # Multiple pages are permitted, subject to the shared daily hard limit.
        return self.paid('search',payload,100)

    def email(self,url):
        return self.paid('email',{'profileUrl':url.strip().lstrip('\ufeff')},10)
