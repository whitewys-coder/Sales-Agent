// Sites enforces private access; caller identity is checked in the MCP route.
// All paid operations remain disabled until original history/ledger migration is verified.
import {type DB,day,rows} from './store';
import {PaidController,confirmMaster,emailPack,requests,type Runtime} from './paid';
export {day,rows};
export type {DB};
export const VERSION='4.2-controlled-paid';
export async function status(db: DB,runtime:Runtime={}) {
 const calls = [...await rows(db,'api_calls'),...await requests(db)]; const drafts = await rows(db,'drafts');
 const settings = await rows(db,'settings');
 const sync = settings.find(x=>x.id==='connector_master_sync');
 const migrated = !!settings.find(x=>x.id==='migration_manifest');
 const masterReview=settings.find(x=>x.id==='paid_master_review');
 return {version:VERSION, paid_enabled:runtime.MCP_PAID_ENABLED==='true', secret_configured:!!runtime.LEADCONTACT_TOKEN, manual_send_only:true, day:day(),
  ledger_migrated:migrated, paid_logic_ported:true, live_acceptance:'not_run', master_review:masterReview||null,
  master_sync:sync||null, credit_plan:100, credit_hard_limit:200,
  used_or_reserved:migrated?calls.filter(x=>x.day===day()).reduce((n,x)=>n+(x.cost??x.reserved??0),0):null,
  unresolved_paid_requests:migrated?calls.filter(x=>x.status!=='completed').length:null,
  total_drafts:migrated?drafts.length:null, pending_drafts:migrated?drafts.filter(x=>x.status==='pending').length:null,
  blockers:[...(!migrated?['原账本未迁移']:[]),...(runtime.MCP_PAID_ENABLED!=='true'?['付费开关关闭']:[]),...(!runtime.LEADCONTACT_TOKEN?['服务端LeadContact密钥未配置']:[]),'真实LeadContact及每日端到端验收尚未完成'],
  verification:'受控付费逻辑已移植；真实接口与每日端到端验收仍待完成'};
}
export async function saveResearch(db:DB, input:any) {
 if(!input || !['company','disposition','reason','next_action'].every(k=>typeof input[k]==='string'&&input[k].trim()))throw Error('Company, disposition, reason and next_action required');
 if(!Array.isArray(input.sources)||!input.sources.length||!input.sources.every((u:any)=>typeof u==='string'&&u.startsWith('https://')))throw Error('Actual retrieved HTTPS URLs required');
 const hash = await crypto.subtle.digest('SHA-256',new TextEncoder().encode(input.company.normalize('NFKC').trim().toLowerCase()));
 const id=Array.from(new Uint8Array(hash),v=>v.toString(16).padStart(2,'0')).join('');
 const body={...input,id,updated_at:new Date().toISOString()};
 await db.prepare('INSERT INTO records(kind,id,body) VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body').bind('research',id,JSON.stringify(body)).run();
 return {saved:true,record_id:id,canonical_master_synced:false};
}
export async function queue(db:DB) {return {research:await rows(db,'research'),pending_packs:(await rows(db,'drafts')).filter(x=>x.status==='pending'),canonical_master_synced:false};}
export async function dispatch(db:DB,name:string,args:any,runtime:Runtime={}) {
 if(name==='get_connector_status')return status(db,runtime);
 if(name==='save_company_research')return saveResearch(db,args.record);
 if(name==='get_work_queue')return queue(db);
 const controller=new PaidController(db,runtime);
 if(name==='confirm_master_review')return confirmMaster(db,args);
 if(name==='plan_people_search')return controller.plan(args.payload,args.review,args.email_reserve);
 if(name==='execute_people_search')return controller.search(args.plan_id);
 if(name==='prepare_personal_email_pack')return emailPack(controller,args);
 throw Error('Unknown tool');
}
const object = (properties:any, required:string[]=[])=>({type:'object',properties,required,additionalProperties:false});
const str={type:'string'}; const record={type:'object',additionalProperties:true};
export const tools=[
 {name:'confirm_master_review',description:'Record actual review of latest Library master matching imported ID/version/hash for this Shanghai day; disclose coverage gaps. No API call.',inputSchema:object({reviewed:{type:'boolean'},library_file_id:str,version:{type:'integer'},source_sha256:str,checked_day:str,coverage_note:str},['reviewed','library_file_id','version','source_sha256','checked_day','coverage_note']),annotations:{readOnlyHint:false,destructiveHint:false,openWorldHint:false}},
 {name:'get_connector_status',description:'Read local connector readiness and ledger. Never calls LeadContact.',inputSchema:object({}),annotations:{readOnlyHint:true,openWorldHint:false}},
 {name:'save_company_research',description:'Save source-backed research and next action in D1; does not sync the canonical Library master.',inputSchema:object({record},['record']),annotations:{readOnlyHint:false,destructiveHint:false,openWorldHint:false}},
 {name:'get_work_queue',description:'Read saved research and pending packs. Does not count them as qualified reserve.',inputSchema:object({}),annotations:{readOnlyHint:true,openWorldHint:false}},
 {name:'plan_people_search',description:'Save a reviewed query plan, enforce current master review and protect email credits. No API call.',inputSchema:object({payload:record,review:record,email_reserve:{type:'integer',minimum:10}},['payload','review','email_reserve']),annotations:{readOnlyHint:false,destructiveHint:false,openWorldHint:false}},
 {name:'execute_people_search',description:'Execute a reviewed plan (up to 100 credits), or reuse stored results. Default paid switch is off; ambiguous requests block.',inputSchema:object({plan_id:str},['plan_id']),annotations:{readOnlyHint:false,destructiveHint:false,openWorldHint:true,idempotentHint:false}},
 {name:'prepare_personal_email_pack',description:'Verify company/current responsibility/bilingual copy, query email (10 credits) or reuse cache, and save a manual pack. Default paid switch off. Never sends.',inputSchema:object({request_id:str,account:record,person:record,employment_evidence:{type:'array',items:record},retrieved_urls:{type:'array',items:str},copy:record,target_match:record},['request_id','account','person','employment_evidence','retrieved_urls','copy','target_match']),annotations:{readOnlyHint:false,destructiveHint:false,openWorldHint:true,idempotentHint:false}},
];
