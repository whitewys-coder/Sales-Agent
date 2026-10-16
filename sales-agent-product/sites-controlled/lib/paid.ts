import {type DB,day,rows,get,put,stable,hash,norm,domain,profile} from './store';
export type Runtime={MCP_PAID_ENABLED?:string,LEADCONTACT_TOKEN?:string,MCP_TEST_ALLOWANCE?:string,MCP_TEST_BASE_USED?:string,MCP_TEST_DAY?:string,MCP_TEST_PROFILE_URL?:string};
type Transport=(path:string,payload?:any)=>Promise<any>;
const EU=['Germany','France','Spain','Italy','Netherlands','Belgium','Switzerland','Austria','Hungary','Czechia'];
const SEA=['Singapore','Malaysia','Thailand','Vietnam','Indonesia','Philippines'];
const INDUSTRIES=['Industrial Automation','Machinery','Electrical & Electronic Manufacturing','Automotive','Sporting Goods','Health, Wellness & Fitness','Plastics','Mining & Metals'];
const BLOCKED=new Set(['sent','reported_sent','reported_forwarded','forwarded','bounced','rejected','replied','excluded','handed_off','已发送','用户确认已发送','已回复','已排除','退信冻结','已拒绝']);
export async function requests(db:DB){return (await db.prepare('SELECT body FROM paid_requests').all<{body:string}>()).results.map(x=>JSON.parse(x.body));}
export function http(runtime:Runtime):Transport{return async(path,payload)=>{
 const allowed=['/api/rest/credits','/api/rest/employess/query/advanced','/api/rest/email/query'];
 if(!allowed.includes(path)||!runtime.LEADCONTACT_TOKEN)throw Error('LeadContact configuration unavailable');
 let r:Response;try{r=await fetch('https://api.leadcontact.ai'+path,{method:payload===undefined?'GET':'POST',headers:{Authorization:'Bearer '+runtime.LEADCONTACT_TOKEN,'Content-Type':'application/json'},body:payload===undefined?undefined:JSON.stringify(payload),redirect:'error',signal:AbortSignal.timeout(40000)});}catch{throw Error('LeadContact network outcome uncertain; no retry');}
 if(!r.ok)throw Error('LeadContact HTTP failure; no retry');const result=await r.json() as any;if(result.code!==200)throw Error('LeadContact business failure; no retry');return result.data;
};}
export async function confirmMaster(db:DB,a:any){
 const sync=await get(db,'settings','connector_master_sync');
 if(!sync||a.reviewed!==true||a.library_file_id!==sync.library_file_id||a.version!==sync.revision||a.source_sha256!==sync.source_sha256||a.checked_day!==day()||!a.coverage_note)throw Error('Review latest canonical master and match imported version/hash for this Shanghai day');
 return put(db,'settings',{id:'paid_master_review',day:day(),version:a.version,source_sha256:a.source_sha256,coverage_note:a.coverage_note,reviewed_at:new Date().toISOString()});
}
export class PaidController{
 constructor(public db:DB,public runtime:Runtime={},public transport?:Transport){}
 async state(){const legacy=await rows(this.db,'api_calls'),fresh=await requests(this.db);return [...legacy,...fresh];}
 async context(){
  const sync=await get(this.db,'settings','connector_master_sync'),review=await get(this.db,'settings','paid_master_review');
  if(!await get(this.db,'settings','migration_manifest')||!sync||review?.day!==day()||review.version!==sync.revision||review.source_sha256!==sync.source_sha256)throw Error('Current canonical master/history review required');
  const all=await this.state();
  if(all.some(x=>!x.day||!Number.isInteger(x.cost??x.reserved)||(x.cost??x.reserved)<0))throw Error('Ledger invalid; manual reconciliation required');
  return {all,sync,used:all.filter(x=>x.day===day()).reduce((n,x)=>n+(x.cost??x.reserved),0)};
 }
 async live(){if(this.runtime.MCP_PAID_ENABLED!=='true')throw Error('Paid operations disabled; no LeadContact request made');if(!this.runtime.LEADCONTACT_TOKEN)throw Error('LeadContact secret missing; no request made');}
 async cache(kind:string,payload:any){const all=await this.state();const key=stable(payload);return all.find(x=>x.kind===kind&&x.status==='completed'&&stable(x.payload)===key&&x.result!==undefined);}
 async paid(kind:'search'|'email',payload:any,emailReserve=0){
  const cached=await this.cache(kind,payload);if(cached)return {cached:true,result:cached.result,source_day:cached.day};
  await this.live();const {all,used}=await this.context();
  if(all.some(x=>x.status!=='completed'))throw Error('Unresolved paid request blocks new paid work');
  const reserved=kind==='search'?100:10;
  let limit=200;
  if(this.runtime.MCP_TEST_ALLOWANCE!==undefined){
   const allowance=Number(this.runtime.MCP_TEST_ALLOWANCE),base=Number(this.runtime.MCP_TEST_BASE_USED);
   if(this.runtime.MCP_TEST_DAY!==day()||kind!=='email'||!profile(this.runtime.MCP_TEST_PROFILE_URL)||profile(payload.profileUrl)!==profile(this.runtime.MCP_TEST_PROFILE_URL)||!Number.isInteger(allowance)||allowance!==10||!Number.isInteger(base)||base<0||base+allowance>200)throw Error('Test grant invalid, expired or target mismatch; no API request');
   limit=base+allowance;if(used+reserved>limit)throw Error('Test grant exhausted; no further paid request');
  }
  if(!Number.isInteger(emailReserve)||emailReserve<0||used+reserved+emailReserve>200)throw Error('Daily hard budget including protected email reserve exceeded');
  const io=this.transport||http(this.runtime);const before=(await io('/api/rest/credits')).remainingPoints;
  if(!Number.isInteger(before)||before<reserved+emailReserve)throw Error('Balance unreadable/insufficient including protected email reserve');
  const id=await hash([day(),kind,payload]);const record:any={id,kind,payload,day:day(),reserved,status:'reserved',created_at:new Date().toISOString(),balance_before:before};
  // A single conditional INSERT is the concurrency decision, including all historical reservations.
  const insert=await this.db.prepare(`INSERT INTO paid_requests(id,body) SELECT ?,? WHERE
   NOT EXISTS(SELECT 1 FROM paid_requests WHERE json_extract(body,'$.status')!='completed')
   AND NOT EXISTS(SELECT 1 FROM records WHERE kind='api_calls' AND json_extract(body,'$.status')!='completed')
   AND COALESCE((SELECT SUM(COALESCE(json_extract(body,'$.cost'),json_extract(body,'$.reserved'))) FROM records WHERE kind='api_calls' AND json_extract(body,'$.day')=?),0)
      +COALESCE((SELECT SUM(COALESCE(json_extract(body,'$.cost'),json_extract(body,'$.reserved'))) FROM paid_requests WHERE json_extract(body,'$.day')=?),0)+?+?<=?
   ON CONFLICT(id) DO NOTHING`).bind(id,JSON.stringify(record),record.day,record.day,reserved,emailReserve,limit).run();
  if(insert.meta.changes!==1)throw Error('Concurrent/ambiguous request or budget conflict; no paid request sent');
  const save=async()=>this.db.prepare('UPDATE paid_requests SET body=? WHERE id=?').bind(JSON.stringify(record),id).run();
  try{
   record.result=await io(kind==='search'?'/api/rest/employess/query/advanced':'/api/rest/email/query',payload);
   record.status='response_received';record.response_received_at=new Date().toISOString();await save();
  }catch{record.status='unknown';await save();throw Error('Paid outcome unknown; reservation retained; do not retry');}
  try{const after=(await io('/api/rest/credits')).remainingPoints;
   if(Number.isInteger(after)&&after<=before){record.observed_cost=before-after;record.balance_after=after;if(before-after>reserved)record.cost=before-after;}
   if(!Number.isInteger(after)||after>before||before-after>reserved)throw Error('Unreconciled billing');
   record.cost=before-after;record.balance_after=after;record.status='completed';record.finished_at=new Date().toISOString();await save();
  }catch{record.billing_status='unknown; reservation retained';await save();throw Error('Response saved but billing unresolved; no new paid work or retry');}
  return {cached:false,result:record.result,source_day:record.day};
 }
 async history(a:any,person?:any){
  const keys=new Set([domain(a.domain),domain(a.group_domain)].filter(Boolean));
  for(const kind of ['accounts','contacts','master_accounts','master_contacts'])for(const x of await rows(this.db,kind)){
   const same=norm(x.company)===norm(a.company)||[domain(x.domain||x.website),domain(x.group_domain),domain(x.email?.split('@')[1])].some(k=>k&&keys.has(k))||person&&profile(person.linkedinUrl)&&profile(x.linkedinUrl||x.linkedin_url||x.raw?.LinkedIn)===profile(person.linkedinUrl);
   if(same&&(BLOCKED.has(x.status)||kind==='accounts'&&['pending_review','needs_contact'].includes(x.status)&&x.contact_verified))throw Error('Historical/group/person suppression; no paid request');
  }
 }
 async plan(payload:any,review:any,emailReserve:number){
  if(!payload||Object.keys(payload).some(k=>!['location','currentTitlesOnly','includeRelatedJobTitles','industry','companySize','jobTitle','nextPageToken'].includes(k)))throw Error('Unverified/unsupported API parameter');
  const loc=payload.location;
  if(!Array.isArray(loc)||loc.length!==1||![...EU,...SEA,'China'].includes(loc[0])||payload.currentTitlesOnly!==true)throw Error('One approved country and currentTitlesOnly=true required');
  if(!['direct','europe_channel','sea_channel'].includes(review?.pool)||SEA.includes(loc[0])&&review.pool!=='sea_channel'||review.pool==='europe_channel'&&!EU.includes(loc[0]))throw Error('Approved market/pool required');
  if(!Array.isArray(payload.jobTitle)||!payload.jobTitle.length||payload.jobTitle.length>30||payload.jobTitle.some((x:any)=>typeof x!=='string'||!x.trim()||x.length>150||/\bOR\b|\bAND\b/.test(x)))throw Error('Actual jobTitle array required; no pasted Boolean query');
  if(!Array.isArray(payload.industry)||!payload.industry.length||payload.industry.some((x:any)=>!INDUSTRIES.includes(x)))throw Error('Unverified industry enum');
  if(payload.companySize&&(!Array.isArray(payload.companySize)||payload.companySize.some((x:any)=>!['11_50','51_200','201_500'].includes(x))))throw Error('Unverified companySize enum; omit filter to avoid unjustified size exclusion');
  if(review.history_reviewed!==true||review.business_query_reviewed!==true||!review.reason)throw Error('Explicit historical and business/query pre-review required');
  if(!Number.isInteger(emailReserve)||emailReserve<10)throw Error('Protect at least 10 email credits');
  if(payload.nextPageToken&&!(await this.state()).some(x=>x.kind==='search'&&x.result?.nextPageToken===payload.nextPageToken))throw Error('Actual saved pagination token required');
  if(review.master_review)await confirmMaster(this.db,review.master_review);
  const {used,sync}=await this.context();const cached=await this.cache('search',payload);
  if(!cached&&used+100+emailReserve>200)throw Error('Insufficient budget after protected emails');
  const plan={id:'paid_plan:'+await hash([payload,review,emailReserve,day()]),payload,review,email_reserve:emailReserve,master_revision:sync.revision,master_sha256:sync.source_sha256,expires_at:Date.now()+1800000};
  await put(this.db,'query_plans',plan);return {plan_id:plan.id,cached:!!cached,worst_case_search_credits:cached?0:100,protected_email_credits:emailReserve,paid_enabled:this.runtime.MCP_PAID_ENABLED==='true'};
 }
 async search(id:string){const p=await get(this.db,'query_plans',id);if(!p||p.expires_at<Date.now())throw Error('Unknown/expired plan');const {sync}=await this.context();if(p.master_revision!==sync.revision||p.master_sha256!==sync.source_sha256)throw Error('Master changed; plan invalid');return this.paid('search',p.payload,p.email_reserve);}
}
const SHARED=new Set(['info','contact','contacts','sales','commercial','office','hello','support','service','admin','courrier','enquiry','enquiries','inquiry','inquiries','marketing','purchasing','quality','production','reception','general']);
const FREE=new Set(['gmail.com','qq.com','outlook.com','hotmail.com','yahoo.com','163.com','foxmail.com','web.de']);
export function corporateEmail(email:any,domains:string[]){if(typeof email!=='string'||! /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))return false;const [local,host]=email.toLowerCase().split('@');return domains.includes(host)&&!FREE.has(host)&&!local.split(/[._+\-]/).some(x=>SHARED.has(x));}
export function validateEmailInput(args:any){
 const {account:a,person:p,employment_evidence:ev,retrieved_urls:urls,copy,target_match:match}=args;
 if(!a?.company||!p?.fullName||norm(p.companyName)!==norm(a.company)||!profile(p.linkedinUrl))throw Error('Exact company, named person and personal LinkedIn profile required');
 if(!Array.isArray(urls)||urls.some((u:any)=>typeof u!=='string'||!u.startsWith('https://')))throw Error('Actually retrieved HTTPS sources required');
 const host=domain(a.domain),group=domain(a.group_domain)||host,source=(a.sources||[]).filter((x:any)=>urls.includes(x.url));
 if(!host||!source.some((x:any)=>['company','product','scene'].includes(x.kind)&&domain(x.url)===host)||a.in_scope!==true||a.excluded||!a.technical_fit||!a.fit_reason)throw Error('Official company/task/scope evidence required');
 if(group!==host&&(a.group_verified!==true||!source.some((x:any)=>x.kind==='group'&&[host,group].includes(domain(x.url)))))throw Error('Verified group relationship evidence required');
 const scope=a.pool==='direct'&&(EU.includes(a.country)||a.country==='China'&&source.some((x:any)=>x.kind==='outbound_market'&&Array.isArray(x.markets)&&x.markets.some((m:string)=>[...EU,'USA','South America'].includes(m))))||a.pool==='europe_channel'&&EU.includes(a.country)||a.pool==='sea_channel'&&SEA.includes(a.country);
 if(!scope||['competitor','institution'].includes(a.company_role)||a.pool==='direct'&&!['manufacturer','OEM'].includes(a.company_role))throw Error('Company outside approved market/business role');
 const authentic=(x:any)=>urls.includes(x.url)&&(domain(x.url)===host&&['official_contact','official_appointment'].includes(x.kind)||x.kind==='personal_profile'&&profile(x.url)===profile(p.linkedinUrl));
 const same=(x:any)=>norm(x.name)===norm(p.fullName)&&norm(x.company)===norm(a.company);
 if(!Array.isArray(ev)||!ev.some(x=>authentic(x)&&same(x)&&x.current===true&&x.title&&x.checked_date===day())||ev.some(x=>authentic(x)&&same(x)&&x.current===false))throw Error('Current employment source reviewed today required; conflicts block');
 if(match?.highly_matched!==true||!match.reason||!Array.isArray(match.urls)||!match.urls.length||!match.urls.every((u:string)=>urls.includes(u)&&[host,group,'linkedin.com'].includes(domain(u))))throw Error('High responsibility match and retrieved evidence required');
 if(!copy||!['subject','body','subject_zh','body_zh'].every(k=>typeof copy[k]==='string'&&copy[k].trim())||/[\r\n]/.test(copy.subject+copy.subject_zh))throw Error('Full bilingual copy required before paid lookup');
 return {...a,domain:host,group_domain:group,sources:source,person:p,copy,employment_evidence:ev,target_match:match};
}
export function scoreAccount(a:any){
 const caps:any={trigger:[25],technical_fit:[10,10,5],decision_maker:[4,4,3,2,2],public_email:[3,3,2,2],strategic:[2,2,1]};const points:any={};const urls=new Set(a.sources.map((x:any)=>x.url));
 for(const k of Object.keys(caps)){points[k]=0;const parts=a.score_evidence?.[k];if(Array.isArray(parts)&&parts.length===caps[k].length)parts.forEach((p:any,i:number)=>{if(Number.isInteger(p.points)&&p.points>=0&&p.points<=caps[k][i]&&p.reason&&p.urls?.length&&p.urls.every((u:string)=>urls.has(u)))points[k]+=p.points;});}
 const age=(Date.parse(day())-Date.parse(a.trigger_date))/86400000;const recent=a.recent_trigger_verified===true&&age>=0&&age<=90&&a.sources.some((x:any)=>x.kind==='official_trigger'&&[a.domain,a.group_domain].includes(domain(x.url)));
 points.freshness=recent?(age<=30?15:age<=60?10:5):0;if(!recent)points.trigger=0;
 points.size=a.employees_verified&&Number.isInteger(a.employees)&&a.sources.some((x:any)=>x.kind==='employees')?(a.employees>=10&&a.employees<=500?5:a.employees>=501&&a.employees<=2000?3:a.employees>0?1:0):0;
 if(!a.sources.some((x:any)=>['product','scene'].includes(x.kind)))points.technical_fit=Math.min(points.technical_fit,15);
 return {score:Object.values(points).reduce<number>((n,v)=>n+Number(v),0),score_breakdown:points,recent_trigger_verified:recent};
}
export async function emailPack(controller:PaidController,args:any){
 if(typeof args.request_id!=='string'||args.request_id.length<16||args.request_id.length>128)throw Error('Stable request_id 16–128 characters required');
 const fingerprint=await hash(args);const id='email_pack:'+await hash(args.request_id);const old=await get(controller.db,'email_jobs',id);
 if(old){if(old.fingerprint!==fingerprint)throw Error('request_id conflict');if(old.result)return old.result;if(!await controller.cache('email',{profileUrl:profile(args.person?.linkedinUrl)}))throw Error('Email operation unfinished without completed API cache; inspect saved response, do not retry automatically');}
 const a=validateEmailInput(args);await controller.history(a,args.person);
 await controller.context();const cached=await controller.cache('email',{profileUrl:profile(args.person.linkedinUrl)});if(!cached)await controller.live();
 // Durable reviewed evidence and bilingual copy precede any paid lookup.
 const job={id,fingerprint,account:a,status:'prepared',prepared_at:new Date().toISOString()};
 // Plain INSERT is a compare-and-set: a concurrent identical job cannot overwrite it.
 const claimId=await hash(a.group_domain);
 if(!old)try{await controller.db.batch([controller.db.prepare('INSERT INTO records(kind,id,body) VALUES(?,?,?)').bind('account_claim',claimId,JSON.stringify({id:claimId,job:id,created_at:new Date().toISOString()})),controller.db.prepare('INSERT INTO records(kind,id,body) VALUES(?,?,?)').bind('email_jobs',id,JSON.stringify(job))]);}catch{throw Error('Company/group already claimed or job conflict; no paid lookup');}
 const response=await controller.paid('email',{profileUrl:profile(args.person.linkedinUrl)});
 const cacheAge=(Date.parse(day())-Date.parse(response.source_day))/86400000;
 if(!Number.isFinite(cacheAge)||cacheAge<0||cacheAge>30){const result={status:'needs_contact',reason:'Cached email validity is older than 30 days or unknown; operator refresh review required',cached:true};await put(controller.db,'email_jobs',{...job,status:'needs_contact',result});return result;}
 const chosen=response.result?.sources?.find((s:any)=>s.valid===true&&s.personal===false&&corporateEmail(s.email,[a.domain,a.group_domain]));
 if(!chosen){const result={status:'needs_contact',reason:'No verified named corporate personal work mailbox',request_id:args.request_id,cached:response.cached};await put(controller.db,'email_jobs',{...job,status:'needs_contact',result});return result;}
 const api='https://api.leadcontact.ai/api/rest/email/query';a.sources.push({url:api,kind:'email_api',claim:'Profile-specific API result; validity is not delivery',publisher:'LeadContact'});
 a.score_evidence={...a.score_evidence,public_email:[{points:3,reason:'Exact verified profile and corporate domain',urls:[api]},{points:3,reason:'API valid on source day '+response.source_day,urls:[api]},{points:2,reason:'Matched work responsibility',urls:[api]},{points:2,reason:'Exact verified profile',urls:[api]}]};
 const scoring=scoreAccount(a);const accountId='work_account:'+await hash([norm(a.company),a.domain]);const draftId='work_draft:'+await hash(args.request_id);
 const account={...a,...scoring,id:accountId,status:'pending_review',contact:args.person.fullName,linkedin_url:profile(args.person.linkedinUrl),email:chosen.email.toLowerCase(),email_valid:true,email_verified:true,email_personal:false,email_domain_match:true,email_business_use:true,contact_verified:true,email_checked_day:response.source_day,rule_version:'4.2'};
 const signedCopy={...args.copy,body:args.copy.body+'\n\nBest regards,\nAlen Wang\nXeroptix\nAlenWang@xeroptix.com\nhttps://xeroptix.com',body_zh:args.copy.body_zh+'\n\nAlen Wang\nXeroptix\nAlenWang@xeroptix.com\nhttps://xeroptix.com'};
 const draft={id:draftId,account_id:accountId,to:account.email,...signedCopy,status:'pending',demo:false,created_at:new Date().toISOString(),channel:scoring.score>=85&&scoring.recent_trigger_verified?'priority':'exploratory'};
 const result={status:'pending',account_id:accountId,draft_id:draftId,score:scoring.score,channel:draft.channel,cached:response.cached,canonical_master_synced:false,manual_send_only:true};
 const entries=[['accounts',account],['drafts',draft],['email_jobs',{...job,status:'completed',result}]] as const;
 await controller.db.batch(entries.map(([kind,value])=>controller.db.prepare('INSERT INTO records(kind,id,body) VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body').bind(kind,value.id,JSON.stringify(value))));return result;
}
