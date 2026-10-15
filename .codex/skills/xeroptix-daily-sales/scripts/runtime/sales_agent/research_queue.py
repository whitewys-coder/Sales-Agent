"""Persist reviewed outcomes separately from the outstanding research queue."""
from .rules import norm
from .store import now

OUTCOMES = {'draft_ready', 'existing_draft', 'needs_contact', 'needs_verification',
            'identity_conflict', 'excluded', 'observe', 'historical_suppression'}

def checkpoint(db, company, outcome, reason, sources, account_id=''):
    if outcome not in OUTCOMES or not reason.strip() or not sources:
        raise ValueError('Reviewed outcome, reason and source URLs required')
    queue = db.get('settings', 'native_research_queue')
    if not queue:
        return False
    key = norm(company)
    remaining = [x for x in queue['value'] if norm(x['company']) != key]
    if len(remaining) == len(queue['value']):
        return False
    # Write the audit record first: interruption cannot silently lose research.
    db.put('settings', {'id': 'research_outcome:' + queue['run_id'] + ':' + key,
        'run_id': queue['run_id'], 'company': company, 'outcome': outcome,
        'reason': reason, 'sources': sorted(set(sources)), 'account_id': account_id,
        'reviewed_at': now()})
    queue.update(value=remaining, updated_at=now())
    db.put('settings', queue)
    run = db.get('runs', queue['run_id'])
    if run:
        records = [x for x in db.all('settings')
                   if x['id'].startswith('research_outcome:') and x.get('run_id') == run['id']]
        run.update(researched_companies=len(records), pending_companies=len(remaining),
                   new_drafts=sum(x['outcome'] == 'draft_ready' for x in records))
        if not remaining:
            run.update(status='research_reviewed', finished_at=now(),
                       note='Company review completed; unresolved contacts remain explicit. Master/ledger writeback is a separate required step.')
        db.put('runs', run)
    return True
