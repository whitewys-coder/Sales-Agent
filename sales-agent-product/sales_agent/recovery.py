"""Offline recovery inventory and SQLite-consistent checkpoints; never calls APIs."""
import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from .rules import norm, email_eligible


def inspect(path, timezone='Asia/Shanghai'):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError('Established database missing; restore before paid work')
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as con:
        integrity = con.execute('PRAGMA quick_check').fetchone()[0]
        def rows(table):
            return [json.loads(r[0]) for r in con.execute(f'SELECT body FROM {table}')]
        settings, runs, calls = rows('settings'), rows('runs'), rows('api_calls')
        queue = next((x for x in settings if x['id'] == 'native_research_queue'), {})
        day = datetime.now(ZoneInfo(timezone)).date().isoformat()
        daily = [x for x in calls if x.get('day') == day]
        accounts, contacts, drafts = rows('accounts'), rows('contacts'), rows('drafts')
        latest = {}
        for x in sorted(settings, key=lambda x: x.get('reviewed_at','')):
            if x['id'].startswith('research_outcome:'):
                latest[norm(x.get('company'))] = x
        stopped={'sent','replied','reported_sent','reported_forwarded','rejected','bounced',
                 '已发送','已回复','用户确认已发送','已拒绝','退信冻结','已退信'}
        suppressed={norm(x.get('company')) for x in accounts+contacts if x.get('status') in stopped}
        unresolved = [x for key,x in latest.items() if key not in suppressed
                      and x.get('outcome') in ('needs_contact', 'needs_verification', 'identity_conflict')]
        pending_drafts=[d for d in drafts if d.get('status') in ('pending','approved') and not d.get('demo')]
        ready=[d for d in pending_drafts if d.get('subject_zh') and d.get('body_zh') and
               any(a['id']==d.get('account_id') and a.get('status') not in stopped and email_eligible(a)
                   for a in accounts)]
        pending = queue.get('value', [])
        interrupted = [r['id'] for r in runs if r['status'] in ('running', 'interrupted')]
        ambiguous = [x['id'] for x in calls if x.get('status') != 'completed']
        return dict(day=day, integrity=integrity, pending_companies=[x['company'] for x in pending],
                    unresolved_reviews=[{'company': x['company'], 'outcome': x['outcome'],
                                         'reason': x['reason']} for x in unresolved],
                    interrupted_runs=interrupted, ambiguous_paid_requests=ambiguous,
                    recorded_credits=sum(x.get('cost', x['reserved']) for x in daily),
                    runtime_drafts=len(drafts), pending_drafts=len(pending_drafts),
                    ready_personal_bilingual_drafts=len(ready), network_calls=0,
                    next_action='resume_research' if pending else 'review_unresolved_and_verify_writeback',
                    writeback_status='must_verify_against_current_library_versions',
                    paid_retry_allowed=False)


def backup(path, destination):
    source, target = Path(path).resolve(), Path(destination).resolve()
    if not source.is_file() or source == target:
        raise ValueError('Existing source and distinct backup path required')
    target.parent.mkdir(parents=True, exist_ok=True)
    # Never expose private lead records through default file permissions.
    temporary = target.with_name(target.name + '.partial')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
            with sqlite3.connect(temporary) as dst:
                src.backup(dst)
                if dst.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup integrity check failed')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return {'backup_created': True, 'network_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--backup')
    args = parser.parse_args()
    if args.backup:
        backup(args.database, args.backup)
    print(json.dumps(inspect(args.database), ensure_ascii=False))

