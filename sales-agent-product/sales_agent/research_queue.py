"""Persist reviewed outcomes separately from the outstanding research queue."""
from .rules import norm
from .store import now

OUTCOMES = {'draft_ready', 'existing_draft', 'needs_contact', 'needs_verification',
            'identity_conflict', 'excluded', 'observe', 'historical_suppression'}

def checkpoint(db, company, outcome, reason, sources, account_id=''):
    if outcome not in OUTCOMES or not reason.strip() or not sources:
        raise ValueError('Reviewed outcome, reason and source URLs required')
    # Outcome, queue removal and run totals commit together across processes.
    import json
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        def get(table, ident):
            row = con.execute(f'SELECT body FROM {table} WHERE id=?', (ident,)).fetchone()
            return json.loads(row[0]) if row else None
        def put(table, item):
            con.execute(f'INSERT INTO {table} VALUES (?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                        (item['id'], json.dumps(item, ensure_ascii=False)))
        queue = get('settings', 'native_research_queue')
        if not queue:
            return False
        key = norm(company)
        remaining = [x for x in queue['value'] if norm(x['company']) != key]
        if len(remaining) == len(queue['value']):
            return False
        put('settings', {'id': 'research_outcome:' + queue['run_id'] + ':' + key,
            'run_id': queue['run_id'], 'company': company, 'outcome': outcome,
            'reason': reason, 'sources': sorted(set(sources)), 'account_id': account_id,
            'reviewed_at': now()})
        queue.update(value=remaining, updated_at=now())
        put('settings', queue)
        run = get('runs', queue['run_id'])
        if run:
            records = [json.loads(x[0]) for x in con.execute('SELECT body FROM settings')]
            records = [x for x in records if x['id'].startswith('research_outcome:')
                       and x.get('run_id') == run['id']]
            run.update(researched_companies=len(records), pending_companies=len(remaining),
                       new_drafts=sum(x['outcome'] == 'draft_ready' for x in records),
                       last_progress_at=now())
            if not remaining:
                run.update(status='research_reviewed', finished_at=now(),
                           note='Company review completed; unresolved contacts remain explicit. Master/ledger writeback is a separate required step.')
            put('runs', run)
    return True
