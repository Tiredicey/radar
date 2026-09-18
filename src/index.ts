import {Hono} from 'hono'
import {serveStatic} from 'hono/cloudflare-workers'
import {secureHeaders} from 'hono/secure-headers'
import {parseFeed,relevant} from './core.js'
import feeds from '../feeds.json'
const app=new Hono<{Bindings:{DB:D1Database}}>()
app.use('*',secureHeaders({contentSecurityPolicy:{defaultSrc:["'self'"],scriptSrc:["'self'"],styleSrc:["'self'"],objectSrc:["'none'"],frameAncestors:["'none'"]},referrerPolicy:'no-referrer'}))
app.use('/static/*',serveStatic({root:'./public'}))
app.get('/',c=>c.redirect('/static/'))
app.get('/favicon.ico',c=>c.redirect('/static/favicon.svg'))
app.get('/api/health',async c=>{await c.env.DB.prepare('SELECT id FROM cache LIMIT 1').first();return c.json({ok:true,storage:'D1'})})
app.get('/api/leads',async c=>{
 const db=c.env.DB,now=Date.now(),lock=await db.prepare('UPDATE lease SET until=? WHERE id=1 AND until<?').bind(now+90000,now).run()
 if(lock.meta.changes){
  try{await Promise.all(feeds.map(async f=>{
   const old=await db.prepare('SELECT * FROM cache WHERE id=?').bind(f.id).first<any>()
   if(old&&now-old.checked<10800000)return
   try{
    const r=await fetch(f.url,{signal:AbortSignal.timeout(12000)})
    if(!r.ok||!r.body)throw Error('Feed unavailable')
    const reader=r.body.getReader(),decoder=new TextDecoder();let xml='',size=0
    while(true){const chunk=await reader.read();if(chunk.done)break;size+=chunk.value.length;if(size>1500000){await reader.cancel();throw Error('Feed too large')}xml+=decoder.decode(chunk.value,{stream:true})}
    xml+=decoder.decode()
    await db.prepare('INSERT OR REPLACE INTO cache VALUES(?,?,?,?,?)').bind(f.id,JSON.stringify(await parseFeed(xml,f.id)),now,1,null).run()
   }catch{await db.prepare('INSERT OR REPLACE INTO cache VALUES(?,?,?,?,?)').bind(f.id,old?.payload||'[]',now,0,'Source check failed. Prior results retained.').run()}
  }))}finally{await db.prepare('UPDATE lease SET until=0 WHERE id=1').run()}
 }
 const {results}=await db.prepare('SELECT * FROM cache').all<any>()
 const items=[...new Map(results.flatMap(r=>JSON.parse(r.payload)).filter(i=>Date.parse(i.published)>now-30*86400000&&relevant(i.title+" "+i.summary)).map(i=>[i.id,i])).values()]
 return c.json({items,sources:feeds.map(f=>({...f,health:(()=>{const r=results.find(r=>r.id===f.id);return r?{checked:r.checked,ok:r.ok,error:r.error,count:JSON.parse(r.payload).length}:null})()})),checking:!lock.meta.changes})
})
app.notFound(c=>c.json({error:'Not found'},404))
app.onError((error,c)=>{console.error(error.name);return c.json({error:'Service unavailable. Stored data is retained.'},503)})
export default app
