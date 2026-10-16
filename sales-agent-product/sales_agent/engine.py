import hashlib
import json
import threading
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from .config import Config
from .store import Store, now, uid
from .provider import Provider
from .mail import Mailbox
from .agents import ValidationAgent, ScoringAgent, SalesAgent, FollowUpAgent
from .agents.validation import evidence_gate
from .leadcontact import LeadContact
from .agents.enrichment import EnrichmentAgent
from .rules import research_eligible, norm

DEFAULT_SCOPE = ('European manufacturing in Germany, France, Spain, Italy, Netherlands, Belgium, Switzerland, '
                 'Austria, Hungary, Czechia; Chinese manufacturers expanding into Europe, USA or South America. '
                 'Industries: manufacturing, energy, automotive, smart hardware, industrial equipment.')


def digest(d):
    return hashlib.sha256(json.dumps({k: d[k] for k in ('to', 'subject', 'body')},
                                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Engine:
    def __init__(self, config, provider=None, mailbox=None, leadcontact=None):
        self.c = config
        self.db = Store(Path(config.data_dir) / (config.mode + '.sqlite3'))
        self.p = provider or Provider(config)
        self.mailbox = mailbox or Mailbox(config)
        self.lock = threading.Lock()
        self.followup = FollowUpAgent(self.p, self.mailbox, self.db)
        self.validation = ValidationAgent(self.p)
        self.scoring = ScoringAgent()
        self.lc = leadcontact or LeadContact(config, self.db)
        self.enrichment = EnrichmentAgent(self.p, self.lc)
        self.sales = SalesAgent(self.p, config)

    def state(self):
        return {'mode': self.c.mode, 'busy': self.lock.locked(),
                'configured': bool(self.c.leadcontact_token and (self.c.research_backend=='native' or self.c.api_key and self.c.model)),
                'rule_version':'3.3','manual_send_only':True,'research_backend':self.c.research_backend,
                'missing_configuration':[name for name,value in ([('LEADCONTACT_TOKEN',self.c.leadcontact_token)] if self.c.research_backend=='native' else [('OPENAI_API_KEY',self.c.api_key),('OPENAI_MODEL',self.c.model),('LEADCONTACT_TOKEN',self.c.leadcontact_token)]) if not value],
                'api_calls':[{k:v for k,v in x.items() if k not in ('result','payload')} for x in self.db.all('api_calls')],
                'schedule_enabled': self.c.schedule_enabled, 'timezone': self.c.timezone,
                'schedule_hour': self.c.schedule_hour,
                'accounts': self.db.all('accounts'), 'drafts': self.db.all('drafts'),
                'runs': self.db.all('runs')[:50], 'events': self.db.all('events')[:100],
                'settings': self.db.all('settings')}

    def known(self, a):
        keys = {a.get('domain'), a.get('group_domain')} - {None, ''}
        if any(x.get('linkedin_key') and x.get('linkedin_key')==a.get('linkedin_key') for x in self.db.all('contacts')):return True
        return any(keys & {x.get('domain'), x.get('group_domain')} for x in self.db.all('accounts')) or any(
            x.get('domain') in keys or x['id'] == a.get('email') for x in self.db.all('contacts'))

    def stage(self, agent, run_id, fn):
        self.db.event(agent, 'running', 'Started', run_id)
        try:
            value = fn()
        except Exception as exc:
            self.db.event(agent, 'failed', type(exc).__name__ + ': ' + str(exc)[:300], run_id)
            raise
        self.db.event(agent, 'completed', 'Completed', run_id)
        return value

    def run(self, scope=DEFAULT_SCOPE, schedule_key=''):
        if not self.lock.acquire(blocking=False):
            raise ValueError('Another run or send is in progress')
        run = {'id': uid(), 'started_at': now(), 'status': 'running', 'mode': self.c.mode,
               'schedule_key': schedule_key, 'scope': scope, 'new_accounts': 0, 'new_drafts': 0}
        self.db.put('runs', run)
        try:
            self.c.check_live()
            if self.c.mode == 'demo':
                self.demo(run)
            else:
                if self.c.research_backend == 'native':
                    queued = self.db.get('settings', 'native_research_queue')
                    if queued and queued.get('value'):
                        run.update(status='awaiting_native_research', resumed_run_id=queued.get('run_id'),
                                   pending_companies=len(queued['value']))
                        return run
                if self.c.mail_sync_enabled:
                    self.stage(self.followup.name, run['id'], self.followup.run)
                else:
                    self.db.event('Follow-up Agent','skipped','Mailbox sync not configured; known local history only',run['id'])
                setting=self.db.get('settings','search_payload')
                if not setting:
                    raise ValueError('Configure a reviewed single-country search_payload before paid discovery')
                result=self.stage('LeadContact Discovery',run['id'],lambda:self.lc.search(setting['value']))
                companies={}
                for person in result.get('employees',[]):
                    name=person.get('companyName','').strip()
                    if name:companies.setdefault(norm(name),{'company':name,'people':[]})['people'].append(person)
                run['returned_people']=len(result.get('employees',[]))
                run['discovered_companies']=len(companies)
                if self.c.research_backend=='native':
                    day=datetime.now(ZoneInfo(self.c.timezone)).date().isoformat()
                    reviewed={norm(x.get('company')) for x in self.db.all('settings') if x['id'].startswith('research_outcome:') and x.get('reviewed_at','')[:10]==day}
                    queue=[x for x in companies.values() if norm(x['company']) not in reviewed and not any(norm(c.get('company'))==norm(x['company']) for c in self.db.all('contacts')) and not any(norm(a.get('discovered_company',a.get('company')))==norm(x['company']) and a.get('status')!='needs_contact' for a in self.db.all('accounts'))]
                    self.db.put('settings',{'id':'native_research_queue','value':queue,'run_id':run['id'],'created_at':now(), 'note':'Discovery only; awaiting current ChatGPT Work research and reviewed bridge completion'})
                    run['status']='awaiting_native_research'
                    return run
                # Resume saved company work before new research; never discard facts after transient failures.
                pending=[x for x in self.db.all('accounts') if x.get('status')=='needs_contact']
                candidates=list(companies.values())
                if self.c.max_accounts:
                    candidates=candidates[:self.c.max_accounts]
                for candidate in candidates:
                    existing=next((x for x in self.db.all('accounts') if norm(x.get('discovered_company',x.get('company')))==norm(candidate['company'])),None)
                    if existing or any(norm(c.get('company'))==norm(candidate['company']) for c in self.db.all('contacts')):continue
                    a=self.stage(self.validation.name,run['id'],lambda:self.validation.run(candidate,scope))
                    if self.known(a):continue
                    a.update(id=uid(),updated_at=now(),demo=False)
                    self.scoring.run(a);self.db.put('accounts',a);run['new_accounts']+=1
                    if research_eligible(a):pending.append(a)
                for a in pending:
                    try:
                        a=self.stage(self.enrichment.name,run['id'],lambda:self.enrichment.run(a))
                        self.scoring.run(a);self.db.put('accounts',a)
                        if any(d.get('account_id')==a['id'] for d in self.db.all('drafts')):continue
                        draft=self.stage(self.sales.name,run['id'],lambda:self.sales.run(a))
                        if draft:self.db.put('drafts',draft);run['new_drafts']+=1
                    except Exception as exc:
                        a['last_error']=type(exc).__name__+': '+str(exc)[:200]
                        self.db.put('accounts',a)
                        run['partial_errors']=run.get('partial_errors',0)+1
            run['status'] = 'partial' if run.get('partial_errors') else 'completed'
        except Exception as exc:
            run.update(status='failed', error=type(exc).__name__ + ': ' + str(exc)[:300])
        finally:
            run['finished_at'] = now()
            self.db.put('runs', run)
            self.lock.release()
        return run

    def demo(self, run):
        for name in ('Follow-up Agent', 'Research Agent'):
            self.db.event(name, 'demo', 'Synthetic fixture; no network/mailbox access', run['id'])
        a = {'id': 'demo-factory', 'company': 'DEMO • Example Factory', 'domain': 'factory.example',
             'group_domain': 'factory.example', 'country': 'Germany', 'employees': 120,
             'trigger': 'Synthetic equipment upgrade, not a real sales lead', 'trigger_date': date.today().isoformat(),
             'contact': 'Demo Director', 'email': 'sales@factory.example', 'technical_fit': True,
             'contact_verified': True, 'email_verified': True, 'strategic': True, 'validated': True,
             'sources': [], 'validation_issues': [], 'evidence_review_required': True,
             'demo': True, 'why_now': 'Synthetic demonstration', 'fit_reason': 'Demonstration only'}
        self.db.event('Validation Agent', 'demo', 'Synthetic evidence only; cannot be sent', run['id'])
        if self.db.get('accounts', a['id']):
            self.db.event('Scoring Agent', 'demo', 'Existing fixture retained (idempotent)', run['id'])
            self.db.event('Sales Agent', 'demo', 'Existing fixture retained (idempotent)', run['id'])
            return
        self.scoring.run(a)
        a.update(validated=True,status='pending_review')
        self.db.put('accounts', a)
        self.db.event('Scoring Agent', 'demo', 'Deterministic score calculated', run['id'])
        d = dict(id='demo-draft', account_id=a['id'], to=a['email'], subject='DEMO — Edge AI pilot',
                 body='Synthetic demonstration only. No real customer or email will be contacted.',
                 status='pending', created_at=now(), approved_hash='', demo=True)
        self.db.put('drafts', d)
        self.db.event('Sales Agent', 'demo', 'Synthetic draft prepared; sending disabled', run['id'])
        run.update(new_accounts=1, new_drafts=1)

    def edit(self, ident, subject, body):
        with self.lock:
            d = self.db.get('drafts', ident)
            if not d or d['status'] not in ('pending', 'approved'):
                raise ValueError('Draft cannot be edited')
            if not subject.strip() or not body.strip() or '\n' in subject or '\r' in subject:
                raise ValueError('Invalid subject or body')
            d.update(subject=subject[:300], body=body[:20000], status='pending', approved_hash='')
            return self.db.put('drafts', d)

    def approve(self, ident, expected_hash, evidence_reviewed):
        with self.lock:
            d = self.db.get('drafts', ident)
            if not d or d['status'] not in ('pending', 'approved'):
                raise ValueError('Draft is not pending')
            if not evidence_reviewed or digest(d) != expected_hash:
                raise ValueError('Review evidence and current draft before approval')
            a = self.db.get('accounts', d['account_id'])
            if not a.get('validated') or a['status'] != 'pending_review':
                raise ValueError('Account not eligible')
            d.update(status='approved', approved_hash=digest(d), approved_at=now())
            self.db.put('drafts', d)
            self.db.event('Sales Agent', 'approved', 'Human approved immutable draft ' + ident)
            return d

    def send(self, ident):
        raise ValueError('Manual sending only. Export/copy the draft to your email client.')

    def report_sent(self, ident, evidence, report_type='sent'):
        with self.lock:
            if report_type not in ('sent','forwarded') or not evidence.strip():
                raise ValueError('Explicit manual sending/forwarding report and evidence required')
            d=self.db.get('drafts',ident)
            if not d or d.get('demo') or d['status'] not in ('pending','approved'):
                raise ValueError('No reportable real draft')
            if not self.db.get('accounts',d['account_id']).get('validated'):
                raise ValueError('Account not eligible for contact')
            d.update(status='reported_'+report_type,reported_at=now(),report_evidence=evidence[:2000])
            self.db.put('drafts',d)
            a=self.db.get('accounts',d['account_id']);a['status']=d['status'];self.db.put('accounts',a)
            self.db.put('contacts',{'id':d['to'],'domain':a['domain'],'group_domain':a['group_domain'],'status':d['status']})
            return d

    def feedback(self, ident, valid, reason):
        with self.lock:
            a = self.db.get('accounts', ident)
            if not a:
                raise ValueError('Unknown account')
            a['feedback'] = {'valid': valid, 'reason': reason[:2000], 'time': now()}
            self.db.put('accounts', a)
            return a
