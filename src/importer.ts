import {Hono} from 'hono'
import {bodyLimit} from 'hono/body-limit'
import {timingSafeEqual} from 'hono/utils/buffer'
import {parseFeed} from './core.js'
import feeds from '../feeds.json'
export const importer=new Hono<{Bindings:{DB:D1Database;SYNC_TOKEN?:string}}>()
importer.post('/:id',async(c,next)=>{
 const secret=c.env.SYNC_TOKEN
 if(!secret||secret.length<32)return c.json({error:'Collector synchronization is not configured.'},503)
 if(!await timingSafeEqual(c.req.header('Authorization')||'',`Bearer ${secret}`))return c.json({error:'Unauthorized'},401)
 if(!feeds.some(f=>f.id===c.req.param('id')))return c.json({error:'Unknown source'},400)
 await next()
},bodyLimit({maxSize:1500000,onError:c=>c.json({error:'Feed too large'},413)}),async c=>{
 const rawTime=c.req.header('X-Collected-At'),checked=Number(rawTime),now=Date.now()
 if(!rawTime||!Number.isSafeInteger(checked)||checked>now+60000||checked<now-86400000)return c.json({error:'Invalid collection timestamp'},400)
 let items
 try{items=await parseFeed(await c.req.text(),c.req.param('id'),new Date(checked))}catch{return c.json({error:'Invalid RSS; existing data retained.'},422)}
 const result=await c.env.DB.prepare('INSERT INTO cache(id,payload,checked,ok,error) VALUES(?,?,?,1,NULL) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,checked=excluded.checked,ok=1,error=NULL WHERE excluded.checked>cache.checked').bind(c.req.param('id'),JSON.stringify(items),checked).run()
 return c.json({accepted:true,updated:Boolean(result.meta.changes),source:c.req.param('id'),count:items.length,checked})
})
