import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
import {readFileSync,writeFileSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
const dir=mkdtempSync(tmpdir()+'/xeroptix-migration-test-');
try{
 for(const file of ['service','migration','paid','store']){const src=readFileSync('lib/'+file+'.ts','utf8').replace(/from '\.\/([a-z]+)'/g,"from './$1.mjs'");writeFileSync(dir+'/'+file+'.mjs',ts.transpile(src,{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}));}
 const {migrate,verify,sha}=await import(dir+'/migration.mjs');
 const sqlite=new DatabaseSync(':memory:');
 sqlite.exec(readFileSync('drizzle/0000_flat_ozymandias.sql','utf8'));sqlite.exec(readFileSync('drizzle/0001_greedy_domino.sql','utf8'));
 const db={prepare(sql){return {sql,args:[],bind(...args){this.args=args;return this},async all(){return {results:sqlite.prepare(this.sql).all(...this.args)}},async run(){return sqlite.prepare(this.sql).run(...this.args)}}},async batch(stmts){sqlite.exec('BEGIN');try{for(const s of stmts)await s.run();sqlite.exec('COMMIT')}catch(e){sqlite.exec('ROLLBACK');throw e}}};
 const kinds=['accounts','contacts','drafts','runs','events','messages','settings','api_calls','master_accounts','master_contacts','master_history','master_rows'];
 const record={kind:'contacts',id:'test-sent',body:JSON.stringify({id:'test-sent',status:'reported_sent'})};
 const m={snapshot:'a'.repeat(64),master:{library_file_id:'libfile_0d02093a9c948191b0f5ead2f9547203',version:5},tables:{}};
 for(const k of kinds)m.tables[k]={count:k===record.kind?1:0,sha256:await sha(k===record.kind?record.id+'\t'+record.body+'\n':'')};
 assert.equal((await verify(db,m)).all_match,false);
 await assert.rejects(()=>migrate(db,{action:'commit',manifest:m}),/checksums/);
 await migrate(db,{action:'stage',manifest:m,records:[record]});
 await migrate(db,{action:'stage',manifest:m,records:[record]}); // idempotent staging
 assert.equal((await verify(db,m)).all_match,true);
 const commit=await migrate(db,{action:'commit',manifest:m});assert.equal(commit.all_match,true);assert.equal(commit.paid_enabled,false);
 assert.equal((await migrate(db,{action:'commit',manifest:m})).already_committed,true);
 const newManifest={...m,snapshot:'b'.repeat(64)};await assert.rejects(()=>migrate(db,{action:'commit',manifest:newManifest}),/already active/);
 const sync=JSON.parse(sqlite.prepare("SELECT body FROM records WHERE id='connector_master_sync'").get().body);assert.equal(sync.history_complete,false);
 assert.equal(JSON.parse(sqlite.prepare("SELECT body FROM records WHERE kind='contacts'").get().body).status,'reported_sent');
 console.log('Migration tests passed: partial import blocked; idempotent batches; checksum/count match; atomic commit; sent preservation; no replacement; incomplete history not claimed.');
 sqlite.close();
}finally{rmSync(dir,{recursive:true,force:true});}
