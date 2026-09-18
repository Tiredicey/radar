import {test} from 'node:test'
import assert from 'node:assert/strict'
import {readFile,mkdir,mkdtemp,rm} from 'node:fs/promises'
import {fileURLToPath} from 'node:url'
import {build} from 'esbuild'
import {Miniflare,convertV4MiniflareOptions} from 'miniflare'

const root=fileURLToPath(new URL('../',import.meta.url))
const schema=await readFile(new URL('../migrations/0001_radar.sql',import.meta.url),'utf8')
const token='fixture-only-collector-token-not-production'
const {outputFiles}=await build({bundle:true,write:false,format:'esm',platform:'browser',stdin:{resolveDir:root,contents:`
import app from './src/index.ts'
let outbound=0
globalThis.fetch=()=>{outbound++;throw new Error('Outbound fetch forbidden in collector tests')}
export default {async fetch(request,env,ctx){
 const path=new URL(request.url).pathname
 if(path==='/__fixture/migrate'){
  for(const sql of ${JSON.stringify(schema)}.split(';').filter(s=>s.trim()))await env.DB.prepare(sql).run()
  return Response.json({ok:true})
 }
 if(path==='/__fixture/storage')return Response.json({rows:(await env.DB.prepare('SELECT * FROM cache ORDER BY id').all()).results,lease:(await env.DB.prepare('SELECT * FROM lease').all()).results,outbound})
 return app.fetch(request,env,ctx)
}}`}})
const script=outputFiles[0].text
const collected=()=>Date.now()-120000
const rss=(time,title='Lipa scholarship applications open',description='PHP 50,000 program budget')=>`<rss><channel><item><title>${title}</title><description>${description}</description><link>https://example.org/fixture-scholarship</link><pubDate>${new Date(time).toUTCString()}</pubDate><source url="https://example.org">Fixture institution</source></item></channel></rss>`
async function fixture(t,{secret=token}={}){
 await mkdir(root+'artifacts',{recursive:true})
 const directory=await mkdtemp(root+'artifacts/importer-')
 const options=convertV4MiniflareOptions({modules:true,script,compatibilityDate:'2026-09-01',d1Databases:{DB:'radar-fixture-only'},bindings:secret===null?{}:{SYNC_TOKEN:secret},resourcePersistencePath:directory,cf:false,telemetry:{enabled:false}})
 let runtime=new Miniflare(options)
 t.after(async()=>{await runtime.dispose();await rm(directory,{recursive:true,force:true})})
 const f={
  request:(path,options)=>runtime.dispatchFetch('http://radar.test'+path,options),
  upload:({id='dost',time=collected(),body=rss(time),authorization=`Bearer ${token}`,headers={},...options}={})=>f.request('/api/feeds/'+id,{method:'POST',body,headers:{...(authorization===null?{}:{Authorization:authorization}),...(time===null?{}:{'X-Collected-At':String(time)}),'Content-Type':'application/rss+xml',...headers},...options}),
  storage:async()=>{const r=await f.request('/__fixture/storage');assert.equal(r.status,200);return r.json()},
  restart:async()=>{await runtime.dispose();runtime=new Miniflare(options);await runtime.ready}
 }
 const r=await f.request('/__fixture/migrate');assert.equal(r.status,200)
 return f
}
async function seed(f){const time=collected();const r=await f.upload({time});assert.equal(r.status,200);return {time,before:await f.storage()}}
async function unchanged(f,before,response,status){assert.equal(response.status,status);assert.ok(!(await response.text()).includes(token));assert.deepEqual(await f.storage(),before)}

test('allowed sources persist normalized evidence in local D1',{timeout:20000},async t=>{
 const f=await fixture(t),time=collected()
 for(const id of ['dost','ched','dict','local']){
  const r=await f.upload({id,time});assert.equal(r.status,200)
  assert.deepEqual(await r.json(),{accepted:true,updated:true,source:id,count:1,checked:time})
 }
 const {rows}=await f.storage();assert.equal(rows.length,4)
 for(const row of rows){
  assert.equal(row.checked,time);assert.equal(row.ok,1);assert.equal(row.error,null)
  const items=JSON.parse(row.payload);assert.equal(items.length,1)
  const item=items[0];assert.match(item.id,/^[0-9a-f]{16}$/)
  assert.equal(item.title,'Lipa scholarship applications open');assert.equal(item.publisher,'Fixture institution')
  assert.equal(item.source,row.id);assert.equal(item.publisher_url,'https://example.org/')
  assert.equal(item.link,'https://example.org/fixture-scholarship');assert.deepEqual(item.amount,{value:50000,evidence:'PHP 50,000'})
  assert.equal(item.collected,new Date(time).toISOString());assert.equal(item.published,new Date(Math.floor(time/1000)*1000).toISOString())
  assert.equal(item.local,true);assert.equal(item.signal,true);assert.equal(item.category,'scholarships')
 }
})
test('missing wrong and malformed authorization preserves stored records',{timeout:20000},async t=>{
 const f=await fixture(t),{before}=await seed(f)
 for(const authorization of [null,'Bearer incorrect',`Bearer ${'x'.repeat(token.length)}`,`Basic ${token}`,token])await unchanged(f,before,await f.upload({authorization}),401)
})
for(const secret of [null,'short'])test(`collector ${secret===null?'missing':'short'} secret denies writes`,{timeout:20000},async t=>{
 const f=await fixture(t,{secret}),before=await f.storage()
 await unchanged(f,before,await f.upload(),503)
 const r=await f.request('/api/health');assert.equal(r.status,200);assert.equal((await r.json()).collectorConfigured,false)
})
test('unknown source IDs cannot change existing snapshots',{timeout:20000},async t=>{
 const f=await fixture(t),{before}=await seed(f)
 for(const id of ['unknown','DOST','dost%27'])await unchanged(f,before,await f.upload({id}),400)
})
test('invalid collection timestamps preserve prior records',{timeout:20000},async t=>{
 const f=await fixture(t),{before}=await seed(f)
 for(const time of [null,'','not-a-date','NaN','Infinity','1.5',Number.MAX_SAFE_INTEGER+1,Date.now()+120000,Date.now()-86460000])await unchanged(f,before,await f.upload({time,body:rss(collected())}),400)
})
test('invalid XML and entity declarations cannot replace stored data',{timeout:20000},async t=>{
 const f=await fixture(t),{before}=await seed(f)
 for(const body of ['','<broken>','<html>Unavailable</html>','<rss/>','<!DOCTYPE rss><rss><channel/></rss>','<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss><channel/></rss>'])await unchanged(f,before,await f.upload({body}),422)
})
test('oversized declared and streamed bodies preserve prior snapshots',{timeout:20000},async t=>{
 const f=await fixture(t),{before}=await seed(f),body='x'.repeat(1500001)
 await unchanged(f,before,await f.upload({body,headers:{'Content-Length':String(body.length)}}),413)
 const unicode=rss(collected(),'Scholarship','₱'.repeat(500001))
 assert.ok(unicode.length<1500000);assert.ok(Buffer.byteLength(unicode)>1500000)
 await unchanged(f,before,await f.upload({body:unicode}),413)
 const stream=new ReadableStream({start(controller){for(let i=0;i<16;i++)controller.enqueue(new Uint8Array(100000).fill(120));controller.close()}})
 await unchanged(f,before,await f.upload({body:stream,duplex:'half'}),413)
})
test('valid XML at the exact byte limit is accepted',{timeout:20000},async t=>{
 const f=await fixture(t),prefix='<rss><channel><description>',suffix='</description></channel></rss>'
 const body=prefix+'x'.repeat(1500000-prefix.length-suffix.length)+suffix
 assert.equal(Buffer.byteLength(body),1500000)
 const r=await f.upload({body});assert.equal(r.status,200);assert.equal((await r.json()).count,0)
 assert.equal((await f.storage()).rows[0].payload,'[]')
})
test('duplicate and older uploads preserve newer data; later uploads replace it',{timeout:20000},async t=>{
 const f=await fixture(t),{time,before}=await seed(f)
 for(const candidate of [time,time-1000]){
  const r=await f.upload({time:candidate,body:rss(candidate,'Different scholarship applications open')})
  assert.equal(r.status,200);assert.equal((await r.json()).updated,false)
  assert.deepEqual(await f.storage(),before)
 }
 const later=time+1000,r=await f.upload({time:later,body:rss(later,'Updated scholarship applications open')})
 assert.equal(r.status,200);assert.equal((await r.json()).updated,true)
 const {rows}=await f.storage();assert.equal(rows.length,1);assert.equal(rows[0].checked,later)
 assert.equal(JSON.parse(rows[0].payload)[0].title,'Updated scholarship applications open')
})
test('concurrent unordered uploads leave the newest snapshot stored',{timeout:20000},async t=>{
 const f=await fixture(t),time=collected(),offsets=[4000,1000,5000,0,3000,2000]
 const responses=await Promise.all(offsets.map(offset=>f.upload({time:time+offset,body:rss(time+offset,`Scholarship update ${offset}`)})))
 for(const r of responses){assert.equal(r.status,200);assert.equal((await r.json()).accepted,true)}
 const {rows}=await f.storage();assert.equal(rows.length,1);assert.equal(rows[0].checked,time+5000)
 assert.equal(JSON.parse(rows[0].payload)[0].title,'Scholarship update 5000')
})
test('snapshots survive runtime restart and collector reads never fetch feeds',{timeout:20000},async t=>{
 const f=await fixture(t),{before}=await seed(f)
 await f.restart();assert.deepEqual(await f.storage(),before)
 const health=await f.request('/api/health');assert.equal(health.status,200);assert.equal((await health.json()).collectorConfigured,true)
 const r=await f.request('/api/leads');assert.equal(r.status,200)
 const data=await r.json();assert.equal(data.mode,'collector');assert.equal(data.checking,false)
 assert.deepEqual(data.items,JSON.parse(before.rows[0].payload));assert.equal(data.sources.length,4)
 assert.equal(data.sources.find(s=>s.id==='dost').health.ok,1);assert.equal(data.sources.find(s=>s.id==='dost').health.stale,false)
 assert.equal(data.sources.filter(s=>s.health===null).length,3);assert.deepEqual(await f.storage(),before)
})
test('collector reads stale snapshots without refreshing or hiding their age',{timeout:20000},async t=>{
 const f=await fixture(t),time=Date.now()-7*3600000
 const upload=await f.upload({time});assert.equal(upload.status,200)
 const before=await f.storage(),r=await f.request('/api/leads');assert.equal(r.status,200)
 const data=await r.json();assert.equal(data.items.length,1);assert.equal(data.sources[0].health.stale,true)
 assert.deepEqual(await f.storage(),before)
})
test('valid empty RSS clears only the targeted source snapshot',{timeout:20000},async t=>{
 const f=await fixture(t),{time}=await seed(f)
 const other=await f.upload({id:'ched',time});assert.equal(other.status,200)
 const before=await f.storage(),r=await f.upload({time:time+1000,body:'<rss><channel><title>Fixture feed</title><link>https://example.org</link><description>No items in this fixture</description></channel></rss>'})
 assert.equal(r.status,200);assert.equal((await r.json()).count,0)
 const {rows}=await f.storage();assert.equal(rows.find(r=>r.id==='dost').payload,'[]')
 assert.deepEqual(rows.find(r=>r.id==='ched'),before.rows.find(r=>r.id==='ched'))
})
