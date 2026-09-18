import {test,before,after} from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {chromium,expect} from '@playwright/test'
const assets=Object.fromEntries(await Promise.all(['index.html','app.js','style.css'].map(async name=>[name,await readFile(new URL('../public/static/'+name,import.meta.url),'utf8')])))
const feeds=JSON.parse(await readFile(new URL('../feeds.json',import.meta.url),'utf8'))
const now=new Date().toISOString()
const lead={id:'fixture',title:'Test scholarship applications open',summary:'Test fixture only.',publisher:'Fixture institution',source:'dost',category:'scholarships',local:false,signal:true,published:now,collected:now,amount:{value:0,evidence:''},link:'https://example.org/fixture'}
const snapshot=()=>({items:[{...lead}],sources:feeds.map((f,i)=>({...f,health:{ok:1,stale:false,checked:Date.now(),count:i===0?1:0,error:null}})),mode:'collector',checking:false})
let browser
before(async()=>{browser=await chromium.launch()})
after(async()=>{await browser?.close()})
async function open(t,response=snapshot()){
 const context=await browser.newContext({viewport:{width:1280,height:900}})
 t.after(()=>context.close())
 const page=await context.newPage(),errors=[]
 const c={page,response,status:200,abort:false,requests:[]}
 page.on('pageerror',e=>errors.push(e.message));t.after(()=>assert.deepEqual(errors,[]))
 await page.route('**/*',async route=>{
  const r=route.request(),u=new URL(r.url());assert.equal(u.origin,'https://radar.test')
  if(u.pathname==='/api/leads'){
   c.requests.push(r.method()+' '+u.pathname)
   return c.abort?route.abort('failed'):route.fulfill({status:c.status,json:c.response})
  }
  const name=u.pathname==='/static/'?'index.html':u.pathname.split('/').pop()
  return route.fulfill({status:assets[name]?200:404,body:assets[name]||'',contentType:{'index.html':'text/html','app.js':'text/javascript','style.css':'text/css'}[name]||'text/plain'})
 })
 c.go=async()=>{await page.goto('https://radar.test/static/');await expect(page.locator('#grid')).toHaveAttribute('aria-busy','false')}
 c.refresh=async()=>{await page.locator('#refresh').click();await expect(page.locator('#grid')).toHaveAttribute('aria-busy','false')}
 return c
}
test('collector refresh reloads snapshots; cache copy and singular wording are accurate',async t=>{
 const c=await open(t);await c.go();const p=c.page
 await expect(p.locator('#refresh-help')).toContainText('Refresh reloads the stored snapshot; it does not trigger GitHub Actions.')
 await expect(p.locator('#health')).toHaveText('4 / 4')
 await expect(p.locator('#shown')).toHaveText('Showing 1 of 1 lead')
 await p.locator('[data-view="sources"]').click()
 await expect(p.locator('#sources')).toContainText('silent baseline')
 await expect(p.locator('#sources')).toContainText('Cache retention is best-effort')
 await expect(p.locator('#sources')).not.toContainText('awaits GitHub workflow-write permission')
 await expect(p.locator('#source-grid')).toContainText('1 lead in stored snapshot')
 await c.refresh();assert.deepEqual(c.requests,['GET /api/leads','GET /api/leads'])
})
test('direct and unknown modes have distinct explanations',async t=>{
 const data=snapshot();data.mode='direct';const c=await open(t,data);await c.go()
 await expect(c.page.locator('#refresh-help')).toContainText('three-hour cache')
 await expect(c.page.locator('#refresh-help')).toContainText('60 seconds')
 c.response={...data,mode:undefined};await c.refresh()
 await expect(c.page.locator('#refresh-help')).toContainText('Collection mode has not been confirmed')
})
test('stale failed and missing checks are excluded from fresh counts',async t=>{
 const data=snapshot();data.sources[1].health.stale=true;data.sources[2].health.ok=0;data.sources[3].health=null
 const c=await open(t,data);await c.go();const p=c.page
 await expect(p.locator('#health')).toHaveText('1 / 4')
 await expect(p.locator('#notice')).toContainText('1 source snapshot over six hours old')
 await expect(p.locator('#notice')).toContainText('1 source check failed')
 await expect(p.locator('#notice')).toContainText('1 source not checked')
 await p.locator('[data-view="sources"]').click()
 await expect(p.locator('#source-grid .panel').nth(1).locator('small')).toHaveText('Stale snapshot')
 await expect(p.locator('#source-grid .panel').nth(2)).toContainText('0 leads in retained data')
})
for(const condition of ['missing','failed','http','network','malformed'])test(`${condition} data is unavailable, not zero; recovery clears the warning`,async t=>{
 const data=snapshot();data.items=[];data.sources.forEach(s=>{s.health=condition==='failed'?{...s.health,ok:0,count:0}:null})
 const c=await open(t,data)
 if(condition==='http'){c.status=503;c.response={error:'Service unavailable'}}
 if(condition==='network')c.abort=true
 if(condition==='malformed')c.response={mode:'collector'}
 await c.go()
 for(const id of ['count','total','local','signals'])await expect(c.page.locator('#'+id)).toHaveText('Unavailable')
 await expect(c.page.locator('#grid h3')).toHaveText('Lead data unavailable')
 await expect(c.page.locator('#export')).toBeDisabled()
 c.status=200;c.abort=false;c.response=snapshot();await c.refresh()
 await expect(c.page.locator('#total')).toHaveText('1');await expect(c.page.locator('#notice')).toBeHidden()
})
test('empty successful snapshots show zero while stale snapshots keep warnings',async t=>{
 const data=snapshot();data.items=[];data.sources.forEach(s=>{s.health.count=0})
 const c=await open(t,data);await c.go()
 await expect(c.page.locator('#total')).toHaveText('0');await expect(c.page.locator('#grid h3')).toHaveText('No matching leads')
 data.sources.forEach(s=>{s.health.stale=true});await c.refresh()
 await expect(c.page.locator('#health')).toHaveText('0 / 4');await expect(c.page.locator('#notice')).toContainText('4 source snapshots')
})
test('failed reload retains prior data and unconfirmed-status warning through filtering',async t=>{
 const c=await open(t);await c.go();c.status=503;c.response={error:'Service unavailable'};await c.refresh()
 await expect(c.page.locator('#total')).toHaveText('1')
 await expect(c.page.locator('#notice')).toContainText('current source status is unconfirmed')
 await c.page.locator('#search').fill('no matching fixture');await expect(c.page.locator('#notice')).toBeVisible()
})
test('filter reset and keyboard search/details retain original behavior',async t=>{
 const c=await open(t);await c.go();const p=c.page
 await p.locator('#local-button').click();await expect(p.locator('#count')).toHaveText('0');await expect(p.locator('#total')).toHaveText('1')
 await p.locator('#reset').click();await expect(p.locator('#shown')).toHaveText('Showing 1 of 1 lead')
 await p.keyboard.press('/');await expect(p.locator('#search')).toBeFocused()
 await p.locator('.card-title').focus();await p.keyboard.press('Enter');await expect(p.locator('#detail')).toBeVisible()
 await p.keyboard.press('Escape');await expect(p.locator('#detail')).not.toBeVisible()
})
test('attribution is absent and all views fit mobile/desktop in light/dark',async t=>{
 const c=await open(t);await c.go();const p=c.page
 for(const width of [320,390,768,1280]){
  await p.setViewportSize({width,height:900})
  for(const theme of ['light','dark']){
   await p.evaluate(theme=>document.documentElement.dataset.theme=theme,theme)
   for(const view of ['discover','sources','guide']){
    await p.locator(`[data-view="${view}"]`).click()
    await expect(p.locator('body')).not.toContainText("made by @Atienzas'assistant")
    assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${width}px ${theme} ${view}`)
   }
  }
 }
})
