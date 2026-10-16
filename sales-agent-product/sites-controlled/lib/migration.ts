import {rows,type DB} from './service';
const ALLOWED=['accounts','contacts','drafts','runs','events','messages','settings','api_calls','master_accounts','master_contacts','master_history','master_rows'];
export async function sha(value:string){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value))),v=>v.toString(16).padStart(2,'0')).join('');}
function validateManifest(m:any){
 if(!m||typeof m.snapshot!=='string'||!/^[a-f0-9]{64}$/.test(m.snapshot)||m.master?.library_file_id!=='libfile_0d02093a9c948191b0f5ead2f9547203'||!Number.isInteger(m.master.version)||!m.tables)throw Error('Invalid fixed-source migration manifest');
 if(Object.keys(m.tables).some(k=>!ALLOWED.includes(k))||ALLOWED.some(k=>!m.tables[k]||!Number.isInteger(m.tables[k].count)||m.tables[k].count<0||! /^[a-f0-9]{64}$/.test(m.tables[k].sha256)))throw Error('Invalid table manifest');
}
async function stageRows(db:DB,snapshot:string,kind:string){return (await db.prepare('SELECT id,body FROM migration_stage WHERE snapshot=? AND kind=? ORDER BY id COLLATE BINARY').bind(snapshot,kind).all<{id:string,body:string}>()).results;}
export async function verify(db:DB,m:any,live=false){
 validateManifest(m);const comparisons:any={};
 for(const kind of ALLOWED){
  const r=live?(await db.prepare('SELECT id,body FROM records WHERE kind=? ORDER BY id COLLATE BINARY').bind(kind).all<{id:string,body:string}>()).results:await stageRows(db,m.snapshot,kind);
  // control settings are added at commit and excluded from source checksum.
  const source=r.filter(x=>!(kind==='settings'&&['migration_manifest','connector_master_sync'].includes(x.id)));
  const digest=await sha(source.map(x=>x.id+'\t'+x.body+'\n').join(''));
  comparisons[kind]={count:source.length,sha256:digest,match:source.length===m.tables[kind].count&&digest===m.tables[kind].sha256};
 }
 return {snapshot:m.snapshot,all_match:Object.values(comparisons).every((x:any)=>x.match),tables:comparisons,mode:live?'live':'staging'};
}
export async function migrate(db:DB,input:any){
 const {action,manifest:m}=input;validateManifest(m);
 if(action==='stage'){
  if(!Array.isArray(input.records)||input.records.length<1||input.records.length>40)throw Error('1–40 records per stage batch');
  const stmts=[];
  for(const r of input.records){
   if(!ALLOWED.includes(r.kind)||typeof r.id!=='string'||typeof r.body!=='string'||r.body.length>100000||['migration_manifest','connector_master_sync'].includes(r.id))throw Error('Invalid migration row');
   const parsed=JSON.parse(r.body);if(!parsed||typeof parsed!=='object'||String(parsed.id)!==r.id)throw Error('Record ID mismatch');
   stmts.push(db.prepare('INSERT INTO migration_stage(snapshot,kind,id,body) VALUES(?,?,?,?) ON CONFLICT(snapshot,kind,id) DO UPDATE SET body=excluded.body').bind(m.snapshot,r.kind,r.id,r.body));
  }
  await db.batch(stmts);return {staged:input.records.length,snapshot:m.snapshot,paid_enabled:false};
 }
 if(action==='verify')return verify(db,m,input.live===true);
 if(action==='commit'){
  const old=(await rows(db,'settings')).find(x=>x.id==='migration_manifest');
  if(old){if(old.snapshot!==m.snapshot)throw Error('Another snapshot is already active; no automatic replacement');return {...await verify(db,m,true),already_committed:true};}
  // Never overwrite existing operational state. Research checkpoints use a separate kind.
  for(const kind of ALLOWED)if((await rows(db,kind)).length)throw Error('Target contains existing operational records; explicit merge required');
  const report=await verify(db,m);if(!report.all_match)throw Error('Staging checksums/counts differ; commit blocked');
  const control={id:'migration_manifest',...m,committed_at:new Date().toISOString(),paid_enabled:false};
  const sync={id:'connector_master_sync',revision:m.master.version,library_file_id:m.master.library_file_id,source_sha256:m.master.sha256,history_imported:true,history_complete:false,note:'Canonical master and original runtime imported; external mailbox coverage not independently verified. Paid logic migration pending.'};
  // One transactional D1 batch publishes source records and control metadata together.
  const stmts=ALLOWED.map(kind=>db.prepare('INSERT INTO records(kind,id,body) SELECT kind,id,body FROM migration_stage WHERE snapshot=? AND kind=?').bind(m.snapshot,kind));
  stmts.push(db.prepare('INSERT INTO records(kind,id,body) VALUES(?,?,?)').bind('settings','migration_manifest',JSON.stringify(control)));
  stmts.push(db.prepare('INSERT INTO records(kind,id,body) VALUES(?,?,?)').bind('settings','connector_master_sync',JSON.stringify(sync)));
  await db.batch(stmts);return {...await verify(db,m,true),committed:true,paid_enabled:false};
 }
 throw Error('Supported migration actions: stage, verify, commit');
}
