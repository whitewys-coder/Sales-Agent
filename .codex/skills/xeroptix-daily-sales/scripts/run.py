#!/usr/bin/env python3
"""Skill entry point. Preflight and dry-run never access the network."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).parent/'runtime'))
from sales_agent.config import Config,load_env
from sales_agent.rules import verify_current

DEFAULT_ENV='/workspace/scratch/4b0c31530046/Sales-Agent/sales-agent-product/.env'

def preflight(c,env):
    path=(Path(c.data_dir)/(c.mode+'.sqlite3')).resolve()
    result={'rule_version':'3.3','env_file_present':env.is_file(),'runtime_db_present':path.is_file(),
            'backend':c.research_backend,'mode':c.mode,'leadcontact_configured':bool(c.leadcontact_token),
            'independent_model_configured':bool(c.api_key and c.model),'network_calls':0,'paid_calls':0,
            'automatic_run_ready':'not_fully_verified',
            'not_checked':['schedule_execution','credential_validity','actual_balance','current_master_history','library_writeback']}
    if path.is_file():
        day=datetime.now(ZoneInfo(c.timezone)).date().isoformat()
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as con:
            tables={x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            rows=[json.loads(x[0]) for x in con.execute('SELECT body FROM api_calls')] if 'api_calls' in tables else []
        daily=[x for x in rows if x.get('day')==day]
        result.update(day=day,recorded_credits=sum(x.get('cost',x['reserved']) for x in daily),
                      unresolved_requests=sum(x.get('status')!='completed' for x in daily))
    return result

def dry_run():
    import subprocess
    result=subprocess.run([sys.executable,str(Path(__file__).with_name('self_test.py'))],capture_output=True,text=True)
    if result.returncode:raise RuntimeError('Offline self-tests failed: '+result.stderr[-1000:])
    return {'status':'passed','scope':'Offline runtime tests with fake transport; not live API/whole daily job acceptance',
            'network_calls':0,'paid_calls':0,'mail_sent':0,'tests_summary':result.stderr.strip().splitlines()[-1]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['preflight','dry-run','discover','queue','finalize'])
    parser.add_argument('--env',default=os.getenv('XEROPTIX_RUNTIME_ENV',DEFAULT_ENV))
    parser.add_argument('--input')
    args=parser.parse_args()
    if args.command=='dry-run':return dry_run()
    env=Path(args.env).expanduser().resolve()
    if env.is_file():load_env(str(env))
    c=Config.env()
    if args.command=='preflight':return preflight(c,env)
    # Never start a fresh empty ledger after loss of the established runtime.
    if not (Path(c.data_dir)/(c.mode+'.sqlite3')).is_file():
        raise ValueError('Existing runtime database missing; restore history and daily budget before paid work')
    if c.mode!='live':raise ValueError('Real workflow requires explicit live configuration')
    c.research_backend='native'
    from sales_agent.engine import Engine
    e=Engine(c)
    if args.command=='queue':return e.db.get('settings','native_research_queue') or {'status':'no_queue','value':[]}
    c.check_live()
    if args.command=='discover':return e.run()
    if not args.input:raise ValueError('--input is required')
    value=json.loads(Path(args.input).read_text())
    from sales_agent.native_bridge import complete
    return complete(e,value['account'],value['person'],value['employment_evidence'],value['retrieved_urls'],value['copy'],value.get('evidence_reviewed') is True)

if __name__=='__main__':
    try:print(json.dumps(main(),ensure_ascii=False))
    except Exception as exc:
        # Do not dump config, raw HTTP bodies or auth headers.
        print(json.dumps({'status':'blocked','error_type':type(exc).__name__,'reason':str(exc)[:300]},ensure_ascii=False))
        raise SystemExit(1)
