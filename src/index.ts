import {Hono} from 'hono'
import {serveStatic} from 'hono/cloudflare-workers'
import {secureHeaders} from 'hono/secure-headers'
import {parseFeed,relevant} from './core.js'
import feeds from '../feeds.json'
import {importer} from './importer'
const app=new Hono<{Bindings:{DB:D1Database;SYNC_TOKEN?:string}}>()
app.use('*',secureHeaders({contentSecurityPolicy:{defaultSrc:["'self'"],scriptSrc:["'self'"],styleSrc:["'self'"],objectSrc:["'none'"],frameAncestors:["'none'"]},referrerPolicy:'no-referrer'}))
app.use('/static/*',serveStatic({root:'./public'}))
app.get('/',c=>c.redirect('/static/'))
app.get('/favicon.ico',c=>c.redirect('/static/favicon.svg'))
app.route('/api/feeds',importer)
app.get('/api/health',async c=>{await c.env.DB.prepare('SELECT id FROM cache LIMIT 1').first();return c.json({ok:true,storage:'D1',collectorConfigured:Boolean(c.env.SYNC_TOKEN&&c.env.SYNC_TOKEN.length>=32)})})
app.get('/api/leads',async c=>{
 const collectorMode=Boolean(c.env.SYNC_TOKEN&&c.env.SYNC_TOKEN.length>=32)
 const db=c.env.DB,now=Date.now(),lock=collectorMode?{meta:{changes:0}}:await db.prepare('UPDATE lease SET until=? WHERE id=1 AND until<?').bind(now+90000,now).run()
 if(lock.meta.changes){
  try{await Promise.all(feeds.map(async f=>{
   const old=await db.prepare('SELECT * FROM cache WHERE id=?').bind(f.id).first<any>()
   if(old&&now-old.checked<(old.ok?10800000:60000))return
   let phase='fetch',status=0
   try{
    const r=await fetch(f.url,{signal:AbortSignal.timeout(12000),headers:{Accept:'application/rss+xml, application/xml;q=0.9','User-Agent':'CapitalRadar/2.0'}})
    status=r.status
    if(!r.ok||!r.body)throw Error('Feed unavailable')
    phase='read'
    const reader=r.body.getReader(),decoder=new TextDecoder();let xml='',size=0
    while(true){const chunk=await reader.read();if(chunk.done)break;size+=chunk.value.length;if(size>1500000){await reader.cancel();throw Error('Feed too large')}xml+=decoder.decode(chunk.value,{stream:true})}
    xml+=decoder.decode()
    phase='parse'
    const items=await parseFeed(xml,f.id)
    phase='storage'
    await db.prepare('INSERT OR REPLACE INTO cache VALUES(?,?,?,?,?)').bind(f.id,JSON.stringify(items),now,1,null).run()
   }catch{await db.prepare('INSERT OR REPLACE INTO cache VALUES(?,?,?,?,?)').bind(f.id,old?.payload||'[]',now,0,`Source ${phase} failed (HTTP ${status||'unavailable'}). Prior results retained. Retry eligible after 60 seconds.`).run()}
  }))}finally{await db.prepare('UPDATE lease SET until=0 WHERE id=1').run()}
 }
 const {results}=await db.prepare('SELECT * FROM cache').all<any>()
 const items=[...new Map(results.flatMap(r=>JSON.parse(r.payload)).filter(i=>Date.parse(i.published)>now-30*86400000&&relevant(i.title+" "+i.summary)).map(i=>[i.id,i])).values()]
 return c.json({items,sources:feeds.map(f=>({...f,health:(()=>{const r=results.find(r=>r.id===f.id);return r?{checked:r.checked,ok:r.ok,stale:now-r.checked>21600000,error:r.error||(now-r.checked>21600000?'Collection is over six hours old. Check the GitHub publisher run.':null),count:JSON.parse(r.payload).length}:null})()})),checking:!collectorMode&&!lock.meta.changes,mode:collectorMode?'collector':'direct'})
})
app.notFound(c=>c.json({error:'Not found'},404))
app.onError((error,c)=>{console.error(error.name);return c.json({error:'Service unavailable. Stored data is retained.'},503)})
export default app
