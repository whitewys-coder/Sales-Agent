"""Single-tenant, fail-closed boundary for a remotely authenticated Work connector.

No arbitrary HTTP, SQL, shell, mail sending, budget changes or credential tools.
The operator must sync the canonical master before enabling paid operations.
"""
import fcntl
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .native_bridge import complete
from .rules import EU, SEA, norm, person_key
from .store import now, uid


class Connector:
    def __init__(self, engine, paid_enabled=False):
        self.e = engine
        self.paid_enabled = paid_enabled

    @contextmanager
    def serial(self):
        with open(Path(self.e.c.data_dir) / 'connector.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def status(self):
        """Local ledger only. Never refresh a third-party balance implicitly."""
        day = datetime.now(ZoneInfo(self.e.c.timezone)).date().isoformat()
        calls = self.e.db.all('api_calls')
        return {'version': '4.1', 'manual_send_only': True,
                'paid_enabled': self.paid_enabled, 'day': day,
                'hard_limit': self.e.c.credit_hard_limit,
                'used_or_reserved': sum(x.get('cost', x.get('reserved', 0))
                                        for x in calls if x.get('day') == day),
                'unresolved': sum(x.get('status') != 'completed' for x in calls),
                'master_sync': self.e.db.get('settings', 'connector_master_sync'),
                'drafts_pending': sum(x.get('status') == 'pending'
                                     for x in self.e.db.all('drafts'))}

    def ready(self, reserve, email_reserve=0):
        if not self.paid_enabled:
            raise ValueError('Paid operations disabled by operator')
        if self.e.c.mode != 'live' or self.e.c.research_backend != 'native':
            raise ValueError('Connector requires live/native configuration')
        s = self.status()
        sync = s['master_sync'] or {}
        # This record is written by an operator after import, never by an MCP tool.
        if sync.get('day') != s['day'] or not sync.get('revision') or not sync.get('history_complete'):
            raise ValueError('Canonical master/history sync required for this Shanghai day')
        if s['unresolved']:
            raise ValueError('Unresolved paid request; operator reconciliation required')
        if type(email_reserve) is not int or email_reserve < 0:
            raise ValueError('Invalid email reserve')
        if s['used_or_reserved'] + reserve + email_reserve > self.e.c.credit_hard_limit:
            raise ValueError('Daily budget including protected email reserve exceeded')

    def suppressed(self, account):
        keys = {account.get('domain'), account.get('group_domain')} - {None, ''}
        for x in self.e.db.all('contacts') + self.e.db.all('accounts'):
            if x.get('id') == account.get('id'):
                continue
            if keys & {x.get('domain'), x.get('group_domain')} or (
                    norm(account.get('company')) and norm(x.get('company')) == norm(account['company'])):
                return True
        return False

    def save_research(self, record):
        required = ('company', 'disposition', 'reason', 'sources', 'next_action')
        if any(not record.get(k) for k in required):
            raise ValueError('Company, disposition, reason, sources and next_action required')
        if not isinstance(record['sources'], list) or not all(
                isinstance(u, str) and u.startswith('https://') for u in record['sources']):
            raise ValueError('Actual retrieved HTTPS source URLs required')
        with self.serial():
            key = hashlib.sha256(norm(record['company']).encode()).hexdigest()
            value = dict(record, id='connector_research:' + key, updated_at=now())
            self.e.db.put('settings', value)
            return {'saved': True, 'record_id': value['id'],
                    'canonical_master_synced': False}

    def plan_search(self, payload, review, email_reserve):
        allowed = {'currentTitlesOnly', 'includeRelatedJobTitles', 'industry',
                   'companySize', 'location', 'jobTitle', 'company', 'seniority', 'nextPageToken'}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise ValueError('Unsupported search fields')
        locations = payload.get('location', [])
        if not isinstance(locations, list) or len(locations) != 1 or locations[0] not in EU | SEA | {'China'}:
            raise ValueError('One approved country required')
        if payload.get('currentTitlesOnly') is not True:
            raise ValueError('currentTitlesOnly=true required')
        titles = payload.get('jobTitle')
        if not isinstance(titles, list) or not titles or not all(isinstance(t, str) and t.strip() for t in titles):
            raise ValueError('Nonempty supported jobTitle array required')
        for k in ('history_reviewed', 'business_query_reviewed'):
            if review.get(k) is not True:
                raise ValueError('Explicit history and business/query review required')
        if not review.get('reason'):
            raise ValueError('Review reason required')
        # Do not accept model-invented enum values: operator records verified API schema values.
        supported = self.e.db.get('settings', 'connector_supported_search') or {}
        for field in ('industry', 'companySize', 'seniority'):
            if field in payload and (not isinstance(payload[field], list) or
                    any(v not in supported.get(field, []) for v in payload[field])):
                raise ValueError('Search values not verified by operator: ' + field)
        if 'nextPageToken' in payload:
            token = payload['nextPageToken']
            if not token or not any(token == x.get('result', {}).get('nextPageToken')
                                    for x in self.e.db.all('api_calls') if x.get('kind') == 'search'):
                raise ValueError('Pagination token must come from a stored actual response')
        if type(email_reserve) is not int or email_reserve < 10:
            raise ValueError('Protect at least one email query (10 credits)')
        with self.serial():
            self.ready(100, email_reserve)
            value = {'id': 'connector_plan:' + uid(), 'payload': payload, 'review': review,
                     'email_reserve': email_reserve,
                     'expires_at': (datetime.now(ZoneInfo('UTC')) + timedelta(minutes=30)).isoformat()}
            self.e.db.put('settings', value)
            return {'plan_id': value['id'], 'worst_case_search_credits': 100,
                    'protected_email_credits': email_reserve, 'expires_at': value['expires_at']}

    def search(self, plan_id):
        with self.serial():
            p = self.e.db.get('settings', plan_id)
            if not p or not plan_id.startswith('connector_plan:'):
                raise ValueError('Unknown query plan')
            if p.get('result') is not None:
                return {'cached': True, 'result': p['result']}
            if p.get('attempted'):
                raise ValueError('Attempt uncertain; do not retry automatically')
            if datetime.fromisoformat(p['expires_at']) <= datetime.now(ZoneInfo('UTC')):
                raise ValueError('Query plan expired')
            # Reuse successful exact queries across days, before any paid balance request.
            for call in self.e.db.all('api_calls'):
                if call.get('kind') == 'search' and call.get('status') == 'completed' and call.get('payload') == p['payload']:
                    p['result'] = call['result']; self.e.db.put('settings', p)
                    return {'cached': True, 'result': p['result']}
            self.ready(100, p['email_reserve'])
            p['attempted'] = now(); self.e.db.put('settings', p)
            result = self.e.lc.search(p['payload'])
            p['result'] = result; self.e.db.put('settings', p)
            return {'cached': False, 'result': result}

    def prepare_email(self, request_id, account, person, employment_evidence,
                      retrieved_urls, copy, target_match):
        if not isinstance(request_id, str) or not 16 <= len(request_id) <= 128:
            raise ValueError('Stable request_id of 16–128 characters required')
        if target_match.get('highly_matched') is not True or not target_match.get('reason'):
            raise ValueError('Highly matched responsibility evidence required')
        if not target_match.get('urls') or not set(target_match['urls']) <= set(retrieved_urls):
            raise ValueError('Retrieved responsibility sources required')
        if not person_key(person.get('linkedinUrl', '')):
            raise ValueError('Exact LinkedIn personal profile required')
        key = 'connector_email:' + hashlib.sha256(request_id.encode()).hexdigest()
        arguments = [account, person, employment_evidence, retrieved_urls, copy, target_match]
        fingerprint = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest()
        with self.serial():
            old = self.e.db.get('settings', key)
            if old:
                if old['fingerprint'] != fingerprint:
                    raise ValueError('request_id reused with changed arguments')
                if 'result' in old:
                    return old['result']
                raise ValueError('Prior operation uncertain; operator review required')
            if self.suppressed(account):
                raise ValueError('Historical/group duplicate; no paid lookup')
            self.ready(10)
            record = {'id': key, 'fingerprint': fingerprint, 'started_at': now()}
            self.e.db.put('settings', record)
            # complete validates company, current employment and bilingual copy before LC.
            result = complete(self.e, account, person, employment_evidence,
                              retrieved_urls, copy, evidence_reviewed=True)
            record['result'] = result; self.e.db.put('settings', record)
            return result
