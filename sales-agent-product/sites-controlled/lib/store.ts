export type DB=D1Database;
export const day=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
export async function rows(db:DB,kind:string){return (await db.prepare('SELECT body FROM records WHERE kind=?').bind(kind).all<{body:string}>()).results.map(x=>JSON.parse(x.body));}
export async function get(db:DB,kind:string,id:string){const r=await db.prepare('SELECT body FROM records WHERE kind=? AND id=?').bind(kind,id).all<{body:string}>();return r.results[0]?JSON.parse(r.results[0].body):null;}
export async function put(db:DB,kind:string,value:any){await db.prepare('INSERT INTO records(kind,id,body) VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body').bind(kind,value.id,JSON.stringify(value)).run();return value;}
export function stable(v:any):string{if(Array.isArray(v))return '['+v.map(stable).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+stable(v[k])).join(',')+'}';return JSON.stringify(v);}
export async function hash(v:any){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(stable(v)))),x=>x.toString(16).padStart(2,'0')).join('');}
export const norm=(s:any)=>String(s||'').normalize('NFKD').replace(/\p{M}/gu,'').trim().toLocaleLowerCase().replace(/\s+/g,' ');
export function domain(s:any){try{const u=new URL(String(s).includes('://')?s:'https://'+s);return u.protocol==='https:'?u.hostname.toLowerCase().replace(/^www\./,''):'';}catch{return '';}}
export function profile(s:any){try{const u=new URL(s);return u.protocol==='https:'&&(u.hostname==='linkedin.com'||u.hostname==='www.linkedin.com')&&/^\/in\/[^/]+\/?$/.test(u.pathname)?'https://www.linkedin.com'+u.pathname.replace(/\/$/,''):'';}catch{return '';}}
