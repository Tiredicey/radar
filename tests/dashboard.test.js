import {test,before,after} from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {execFileSync} from 'node:child_process'
import {chromium,expect} from '@playwright/test'
const assets=Object.fromEntries(await Promise.all(['index.html','app.js','legal.js','style.css','visuals.js','visuals.css','guide.js','research-guide.webp','research-guide.webm','research-guide.mp4','research-guide.vtt'].map(async name=>[name,await readFile(new URL('../public/static/'+name,import.meta.url))])))
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
 const c={page,response,status:200,abort:false,requests:[],allRequests:[]}
 page.on('pageerror',e=>errors.push(e.message));t.after(()=>assert.deepEqual(errors,[]))
 await page.route('**/*',async route=>{
  const r=route.request(),u=new URL(r.url());c.allRequests.push(r.method()+' '+u.href);assert.equal(u.origin,'https://radar.test')
  if(u.pathname==='/api/leads'){
   c.requests.push(r.method()+' '+u.pathname)
   return c.abort?route.abort('failed'):route.fulfill({status:c.status,json:c.response})
  }
  const name=u.pathname==='/static/'?'index.html':u.pathname.split('/').pop()
  return route.fulfill({status:assets[name]?200:404,body:assets[name]||'',contentType:{'index.html':'text/html','app.js':'text/javascript','legal.js':'text/javascript','visuals.js':'text/javascript','guide.js':'text/javascript','style.css':'text/css','visuals.css':'text/css','research-guide.webp':'image/webp','research-guide.webm':'video/webm','research-guide.mp4':'video/mp4','research-guide.vtt':'text/vtt'}[name]||'text/plain'})
 })
 c.go=async(hash='')=>{await page.goto('https://radar.test/static/'+hash);await expect(page.locator('#grid')).toHaveAttribute('aria-busy','false')}
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
async function downloadCSV(page){
 const pending=page.waitForEvent('download',{timeout:5000})
 await page.locator('#export').click()
 const download=await pending,chunks=[]
 for await(const chunk of await download.createReadStream())chunks.push(chunk)
 assert.equal(await download.failure(),null)
 assert.match(download.suggestedFilename(),/^radar-leads-\d{4}-\d{2}-\d{2}\.csv$/)
 const bytes=Buffer.concat(chunks)
 assert.deepEqual([...bytes.subarray(0,3)],[0xef,0xbb,0xbf])
 return JSON.parse(execFileSync('python3',['-c','import csv,io,json,sys; print(json.dumps(list(csv.reader(io.StringIO(sys.stdin.buffer.read().decode("utf-8-sig"), newline=""), strict=True))))'],{input:bytes,encoding:'utf8',timeout:5000}))
}
const csvHeader=['Title','Publisher','Published','Amount mentioned, not payout','Evidence wording','Source URL']
const csvRow=i=>[i.title,i.publisher,i.published,i.amount.value?String(i.amount.value):'',i.amount.evidence,i.link]
test('CSV exports exactly the filtered results in selected order beyond the visible page',async t=>{
 const data=snapshot(),matches=Array.from({length:16},(_,n)=>({...lead,id:`match-${n}`,title:`Scholarship ${n}`,summary:n%2?'Needle in summary':'Fixture only',publisher:n%2?'Fixture institution':'Needle institution',local:true,published:new Date(Date.parse(now)-n*60000).toISOString(),link:`https://example.org/match-${n}`}))
 data.items=[...matches].reverse().concat([
  {...matches[0],id:'wrong-category',category:'grants'},
  {...matches[0],id:'wrong-location',local:false},
  {...matches[0],id:'no-signal',signal:false},
  {...matches[0],id:'no-search-match',publisher:'Unrelated institution'}
 ])
 const c=await open(t,data);await c.go();const p=c.page
 await p.locator('[data-category="scholarships"]').click()
 await p.locator('#location').selectOption('local');await p.locator('#only-signals').check()
 await p.locator('#search').fill('NEEDLE');await p.locator('#sort').selectOption('new')
 await expect(p.locator('#shown')).toHaveText('Showing 12 of 16 leads')
 await expect(p.locator('#grid .card')).toHaveCount(12)
 assert.deepEqual(await downloadCSV(p),[csvHeader,...matches.map(csvRow)])
 await p.locator('#more').click();await expect(p.locator('#grid .card')).toHaveCount(16)
 assert.deepEqual(await downloadCSV(p),[csvHeader,...matches.map(csvRow)])
 await p.locator('#search').fill('no matching export fixture');await expect(p.locator('#export')).toBeDisabled()
 assert.deepEqual(c.requests,['GET /api/leads'])
})
test('CSV preserves Unicode quotes commas and embedded line breaks with explicit amount evidence',async t=>{
 const data=snapshot()
 data.items=[{...lead,title:'Iskolar "Bukas", José\n第二行',publisher:'Pamantasan, "Lipa"\r\nBatangas',amount:{value:50000,evidence:'₱50,000, "budget"\nnot a payout\rretain CR'},link:'https://example.org/fixture?q=%22Lipa%22&lang=fil'},{...lead,id:'unknown-amount',title:'Unknown amount',link:'https://example.org/unknown'}]
 const c=await open(t,data);await c.go()
 assert.deepEqual(await downloadCSV(c.page),[csvHeader,...data.items.map(csvRow)])
})
test('CSV neutralizes formula prefixes without altering ordinary text',async t=>{
 const values=['=1+1','+1+1','-1+1','@SUM(1,1)','  =1+1','\t+1+1','\rtext','\ntext','\ttext',' \r\n@SUM(1,1)']
 const plain=['Ordinary =1+1','Lipa-Batangas','email@example.org','Already quoted \'text\'','  plain text']
 const data=snapshot();data.items=[...values,...plain].map((value,n)=>({...lead,id:`prefix-${n}`,title:value,publisher:value,amount:{value:0,evidence:value},link:`https://example.org/prefix-${n}`}))
 const c=await open(t,data);await c.go()
 const expected=data.items.map((i,n)=>{const value=n<values.length?"'"+i.title:i.title;return [value,value,i.published,'',value,i.link]})
 assert.deepEqual(await downloadCSV(c.page),[csvHeader,...expected])
})
test('copy-link writes the selected source URL to the permitted browser clipboard',async t=>{
 const data=snapshot();data.items.push({...lead,id:'second',title:'Second scholarship',link:'https://example.org/second?a=1&b=%22Lipa%22#details'})
 const c=await open(t,data);await c.page.context().grantPermissions(['clipboard-read','clipboard-write'],{origin:'https://radar.test'});await c.go();const p=c.page
 for(const item of data.items){
  await p.locator(`.card-title[data-detail="${item.id}"]`).click()
  await p.locator('#copy').click();await expect(p.locator('#toast')).toHaveText('Source link copied.')
  assert.equal(await p.evaluate(()=>navigator.clipboard.readText()),item.link)
  await p.locator('#close').click()
 }
 assert.deepEqual(c.requests,['GET /api/leads'])
})
test('copy-link permission denial retains clipboard and offers the original link without false success',async t=>{
 const c=await open(t);await c.page.context().grantPermissions(['clipboard-read','clipboard-write'],{origin:'https://radar.test'});await c.go();const p=c.page
 await p.evaluate(()=>navigator.clipboard.writeText('untouched fixture clipboard'))
 await p.context().clearPermissions()
 await p.context().grantPermissions([],{origin:'https://radar.test'})
 assert.equal(await p.evaluate(async()=>(await navigator.permissions.query({name:'clipboard-write'})).state),'denied')
 await p.locator('.card-title').click();await p.locator('#copy').click()
 await expect(p.locator('#toast')).toHaveText('Copy unavailable. Use the original source link.')
 await expect(p.locator('#detail a')).toHaveAttribute('href',lead.link)
 await expect(p.locator('#detail')).toBeVisible()
 await p.context().grantPermissions(['clipboard-read','clipboard-write'],{origin:'https://radar.test'})
 assert.equal(await p.evaluate(()=>navigator.clipboard.readText()),'untouched fixture clipboard')
 await p.locator('#copy').click();await expect(p.locator('#toast')).toHaveText('Source link copied.')
 assert.equal(await p.evaluate(()=>navigator.clipboard.readText()),lead.link)
 assert.deepEqual(c.requests,['GET /api/leads'])
})
test('copy-link unavailable API uses the fallback without a page error',async t=>{
 const c=await open(t)
 await c.page.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:undefined,configurable:true}))
 await c.go();await c.page.locator('.card-title').click();await c.page.locator('#copy').click()
 await expect(c.page.locator('#toast')).toHaveText('Copy unavailable. Use the original source link.')
 await expect(c.page.locator('#detail a')).toHaveAttribute('href',lead.link)
})
test('copy-link waits for clipboard completion before reporting success',async t=>{
 const c=await open(t)
 await c.page.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:text=>new Promise(resolve=>{window.clipboardAttempt=text;window.completeClipboard=resolve})},configurable:true}))
 await c.go();await c.page.locator('.card-title').click();await c.page.locator('#copy').click()
 assert.equal(await c.page.evaluate(()=>window.clipboardAttempt),lead.link)
 await expect(c.page.locator('#toast')).toBeHidden()
 await c.page.evaluate(()=>window.completeClipboard());await expect(c.page.locator('#toast')).toHaveText('Source link copied.')
})
test('legal navigation has unique controls, supports hashes and preserves funding filters',async t=>{
 const c=await open(t);await c.go();const p=c.page
 await expect(p.locator('[data-view="discover"]')).toHaveCount(1)
 await p.locator('[data-category="scholarships"]').click();await p.locator('#location').selectOption('local')
 await p.locator('#sort').selectOption('new');await p.locator('#only-signals').check();await p.locator('#search').fill('scholarship')
 await p.locator('[data-view="legal"]').click()
 await expect(p.locator('body')).toHaveAttribute('data-current-view','legal')
 assert.equal(await p.locator('body').getAttribute('data-view'),null)
 await expect(p.locator('[data-view="legal"]')).toHaveAttribute('aria-current','page')
 await expect(p.locator('h1')).toHaveText('Jurisprudence, Traced')
 await expect(p.locator('#breadcrumb')).toHaveText('Jurisprudence, Traced')
 assert.equal(new URL(p.url()).hash,'#legal')
 for(const id of ['refresh','refresh-help','notice','discover'])await expect(p.locator('#'+id)).toBeHidden()
 await p.locator('[data-view="discover"]').click()
 await expect(p.locator('#refresh')).toBeVisible();await expect(p.locator('#refresh-help')).toBeVisible()
 await expect(p.locator('#search')).toHaveValue('scholarship');await expect(p.locator('#location')).toHaveValue('local')
 await expect(p.locator('#sort')).toHaveValue('new');await expect(p.locator('#only-signals')).toBeChecked()
 await expect(p.locator('[data-category="scholarships"]')).toHaveAttribute('aria-pressed','true')
 await p.evaluate(()=>location.hash='legal');await expect(p.locator('#legal')).toBeVisible()
 await p.reload();await expect(p.locator('#legal')).toBeVisible();await expect(p.locator('#grid')).toHaveAttribute('aria-busy','false')
 await expect(p.locator('#refresh')).toBeHidden()
 await p.evaluate(()=>location.hash='not-a-view');await expect(p.locator('#discover')).toBeVisible()
 await expect(p.locator('[data-view="discover"]')).toHaveCount(1)
 await expect(p.locator('[data-view="discover"]')).toHaveAttribute('aria-current','page')
})
test('legal source links encode literal input and never submit queries while preparing',async t=>{
 const c=await open(t);await c.go('#legal');const p=c.page,requests=[...c.allRequests]
 const sources=[['Supreme Court E-Library','elibrary.judiciary.gov.ph','https://elibrary.judiciary.gov.ph/','Official judiciary source'],['Supreme Court','sc.judiciary.gov.ph','https://sc.judiciary.gov.ph/','Official judiciary source'],['Lawphil','lawphil.net','https://lawphil.net/','Nonofficial reference'],['ChanRobles','chanrobles.com','https://www.chanrobles.com/','Nonofficial reference']]
 await expect(p.locator('#legal-links article')).toHaveCount(4)
 await expect(p.locator('#legal-links .button')).toHaveCount(0)
 for(const [i,[name,,home,kind]] of sources.entries()){
  const card=p.locator('#legal-links article').nth(i)
  await expect(card.locator('h3')).toHaveText(name);await expect(card.locator('small')).toHaveText(kind)
  await expect(card.locator('a')).toHaveAttribute('href',home)
 }
 const query='G.R. 12345 "due process" & <img src=x onerror="window.legalInjected=1"> José'
 await p.locator('#legal-query').fill('  '+query+'  ')
 for(const exact of [false,true]){
  await p.locator('#legal-exact').setChecked(exact)
  await p.getByRole('button',{name:'Prepare search links',exact:true}).click()
  await expect(p.locator('#legal-links .button')).toHaveCount(4)
  for(const [i,[,domain]] of sources.entries()){
   const a=p.locator('#legal-links .button').nth(i),url=new URL(await a.getAttribute('href'))
   assert.equal(url.origin,'https://www.google.com');assert.equal(url.pathname,'/search')
   assert.deepEqual([...url.searchParams],[['as_sitesearch',domain],[exact?'as_epq':'as_q',query]])
   await expect(a).toHaveAttribute('target','_blank');await expect(a).toHaveAttribute('rel','noopener noreferrer')
  }
 }
 await p.locator('#legal-query').press('Enter')
 await expect(p.locator('#legal-status')).toHaveText('Search links prepared. Choose a source; results open on Google.')
 await expect(p.locator('#legal img')).toHaveCount(0);assert.equal(await p.evaluate(()=>window.legalInjected),undefined)
 assert.deepEqual(c.allRequests,requests)
 await expect(p.locator('#legal')).toContainText('not a case database or a citator')
 await expect(p.locator('#legal-form')).toContainText('Do not enter confidential client or case details')
})
test('legal glossary has six source-linked entries with keyboard context and truthful filtering',async t=>{
 const c=await open(t);await c.go('#legal');const p=c.page
 const constitution='https://lawphil.net/consti/cons1987.html',handbook='https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/46/63230'
 const citations=[['Due process',constitution,'1987 Constitution, Article III, Section 1'],['Equal protection',constitution,'1987 Constitution, Article III, Section 1'],['Grave abuse of discretion',constitution,'1987 Constitution, Article VIII, Section 1, paragraph 2'],['Ratio decidendi',handbook,'Fundamentals of Decision Writing for Judges, Chapter Three: Ratio Decidendi'],['Obiter dictum',handbook,'Fundamentals of Decision Writing for Judges, Chapter Three: Obiter Dictum'],['Dispositive portion',handbook,'Fundamentals of Decision Writing for Judges, Chapter Three: Dispositive Portion']]
 await expect(p.locator('#legal-terms article')).toHaveCount(6)
 await expect(p.locator('#legal-count')).toHaveText('6 learning entries shown.')
 for(const [i,[name,url,cite]] of citations.entries()){
  const card=p.locator('#legal-terms article').nth(i),details=card.locator('details'),summary=card.locator('summary')
  await expect(card.locator('h3')).toHaveText(name)
  await summary.focus();await p.keyboard.press('Enter');await expect(details).toHaveAttribute('open','')
  await expect(details.locator('a')).toHaveText(cite);await expect(details.locator('a')).toHaveAttribute('href',url)
  await expect(details).toContainText(i<3?'nonofficial reference':'not itself a judicial holding')
  await expect(details).toContainText('Subsequent treatment and current controlling status have not been checked.')
  await expect(details.locator('blockquote')).toHaveCount(i<3?0:1)
  await p.keyboard.press('Space');assert.equal(await details.getAttribute('open'),null)
 }
 await p.locator('#legal-filter').fill('  RATIO DECIDENDI  ')
 await expect(p.locator('#legal-terms h3')).toHaveText('Ratio decidendi')
 await p.locator('#legal-filter').fill('fallo');await expect(p.locator('#legal-terms h3')).toHaveText('Dispositive portion')
 await p.locator('#legal-filter').fill('no such legal entry')
 await expect(p.locator('#legal-terms article')).toHaveCount(0)
 await expect(p.locator('#legal-count')).toHaveText('No matching learning entries. This is a small glossary, not a complete legal index.')
})
test('legal research-this-term and clear reset local research without clearing funding search',async t=>{
 const c=await open(t);await c.go();const p=c.page
 await p.locator('#search').fill('scholarship');await p.locator('[data-view="legal"]').click()
 const requests=[...c.allRequests]
 await p.locator('#legal-exact').check();await p.locator('#legal-filter').fill('ratio decidendi')
 await p.getByRole('button',{name:'Research this term',exact:true}).click()
 await expect(p.locator('#legal-query')).toHaveValue('Ratio decidendi');await expect(p.locator('#legal-query')).toBeFocused()
 await expect(p.locator('#legal-links .button')).toHaveCount(4)
 for(const href of await p.locator('#legal-links .button').evaluateAll(links=>links.map(a=>a.href)))assert.equal(new URL(href).searchParams.get('as_epq'),'Ratio decidendi')
 await p.locator('#legal-clear').click()
 for(const id of ['legal-query','legal-filter'])await expect(p.locator('#'+id)).toHaveValue('')
 await expect(p.locator('#legal-exact')).not.toBeChecked();await expect(p.locator('#legal-query')).toBeFocused()
 await expect(p.locator('#legal-terms article')).toHaveCount(6);await expect(p.locator('#legal-links .button')).toHaveCount(0)
 await expect(p.locator('#legal-status')).toHaveText('Enter a topic or phrase to prepare source-specific search links.')
 await p.locator('#legal-query').fill('   ');await expect(p.locator('#legal-links .button')).toHaveCount(0)
 assert.deepEqual(c.allRequests,requests)
 await p.locator('[data-view="discover"]').click();await expect(p.locator('#search')).toHaveValue('scholarship')
})
test('attribution is absent and all views fit mobile/desktop in light/dark',async t=>{
 const c=await open(t);await c.go();const p=c.page
 for(const width of [320,390,768,1280]){
  await p.setViewportSize({width,height:900})
  for(const theme of ['light','dark']){
   await p.evaluate(theme=>document.documentElement.dataset.theme=theme,theme)
   for(const view of ['discover','sources','guide','legal']){
    await p.locator(`[data-view="${view}"]`).click()
    await expect(p.locator('body')).not.toContainText("made by @Atienzas'assistant")
    assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${width}px ${theme} ${view}`)
   }
  }
 }
})

test('motion controls stop the radar and follow system preferences',async t=>{
 const c=await open(t);await c.go();const p=c.page
 await expect(p.locator('html')).toHaveAttribute('data-motion','on')
 assert.equal(await p.locator('.radar').evaluate(e=>getComputedStyle(e,'::before').animationName),'radar-sweep')
 await p.locator('#motion-toggle').click()
 await expect(p.locator('html')).toHaveAttribute('data-motion','paused')
 await expect(p.locator('#motion-toggle')).toHaveAttribute('aria-pressed','true')
 assert.equal(await p.locator('.radar').evaluate(e=>getComputedStyle(e,'::before').animationName),'none')
 await p.locator('#motion-toggle').click();await p.emulateMedia({reducedMotion:'reduce'})
 await expect(p.locator('#motion-toggle')).toBeDisabled()
 await expect(p.locator('html')).toHaveAttribute('data-motion','paused')
 assert.equal(await p.locator('.radar').evaluate(e=>getComputedStyle(e,'::before').animationName),'none')
 await p.emulateMedia({reducedMotion:'no-preference'})
 await expect(p.locator('#motion-toggle')).toBeEnabled()
 await expect(p.locator('html')).toHaveAttribute('data-motion','on')
})
test('focus mode preserves research filters and essential guidance',async t=>{
 const c=await open(t);await c.go();const p=c.page
 await p.locator('#search').fill('scholarship');await p.locator('#focus-mode').click()
 await expect(p.locator('.hero')).toBeHidden();await expect(p.locator('.card-title')).toBeVisible()
 await p.locator('[data-view="guide"]').click()
 await expect(p.locator('.visual-guide')).toBeHidden();await expect(p.locator('#guide > .panel')).toBeVisible()
 await p.locator('#focus-mode').click();await expect(p.locator('.visual-guide')).toBeVisible()
 await p.locator('[data-view="discover"]').click();await expect(p.locator('#search')).toHaveValue('scholarship')
})
test('guide plays real opt-in video with captions, keyboard isolation and focus recovery',async t=>{
 const c=await open(t);await c.go();const p=c.page
 assert.equal(c.allRequests.some(u=>/research-guide\.(webm|mp4)/.test(u)),false)
 const trigger=p.locator('.watch-guide')
 await trigger.click();await expect(p.locator('#guide-dialog')).toBeVisible()
 assert.equal(await p.locator('#research-video').evaluate(v=>v.paused),true)
 const hash=new URL(p.url()).hash;await p.keyboard.press('/');assert.equal(new URL(p.url()).hash,hash)
 await p.locator('#research-video').evaluate(async v=>{v.textTracks[0].mode='hidden';await v.play()})
 await expect.poll(()=>p.locator('#research-video').evaluate(v=>v.currentTime)).toBeGreaterThan(.1)
 assert.equal(await p.locator('#research-video').evaluate(v=>v.videoWidth),960)
 assert.equal(await p.locator('#research-video').evaluate(v=>Math.round(v.duration)),18)
 await expect.poll(()=>p.locator('#research-video').evaluate(v=>v.textTracks[0].cues?.length||0)).toBe(3)
 await p.keyboard.press('Escape');await expect(p.locator('#guide-dialog')).toBeHidden()
 await expect.poll(()=>p.locator('#research-video').evaluate(v=>v.paused)).toBe(true)
 await expect(trigger).toBeFocused();await trigger.click()
 assert.equal(await p.locator('#research-video').evaluate(v=>v.paused),true)
 await p.locator('#guide-close').click()
})
test('system reduced motion pauses active video without hiding the transcript',async t=>{
 const c=await open(t);await c.go();const p=c.page
 await p.locator('.watch-guide').click();await p.locator('#research-video').evaluate(v=>v.play())
 await p.emulateMedia({reducedMotion:'reduce'})
 await expect.poll(()=>p.locator('#research-video').evaluate(v=>v.paused)).toBe(true)
 await expect(p.locator('#guide-transcript')).toContainText('not a verified open application')
})
test('failed media reports failure while preserving the complete text alternative',async t=>{
 const c=await open(t);await c.page.route('**/research-guide.webm',r=>r.abort());await c.page.route('**/research-guide.mp4',r=>r.abort())
 await c.go();const p=c.page;await p.locator('.watch-guide').click()
 await p.locator('#research-video').evaluate(v=>{v.play().catch(()=>{})})
 await expect(p.locator('#video-status')).toContainText('Video unavailable')
 await expect(p.locator('#guide-transcript')).toBeVisible()
})
test('guide poster and dialog fit mobile desktop and both themes',async t=>{
 const c=await open(t);await c.go('#guide');const p=c.page
 await expect.poll(()=>p.locator('.guide-preview img').evaluate(i=>i.naturalWidth)).toBe(960)
 for(const width of [320,390,768,1280]){
  await p.setViewportSize({width,height:900})
  for(const theme of ['light','dark']){
   await p.evaluate(value=>document.documentElement.dataset.theme=value,theme)
   await p.locator('.guide-preview').click()
   assert.equal(await p.locator('#guide-dialog').evaluate(d=>d.scrollWidth<=d.clientWidth&&d.getBoundingClientRect().right<=innerWidth),true,`${width} ${theme}`)
   await p.locator('#guide-close').click()
  }
 }
})
test('source and lead collection timestamps include exact PHT clock time',async t=>{
 const data=snapshot();data.sources[0].health.checked=Date.parse('2026-09-21T04:34:00Z');data.items[0].collected='2026-09-21T04:34:00Z'
 const c=await open(t,data);await c.go();const p=c.page
 await p.locator('[data-view="sources"]').click();await expect(p.locator('#source-grid .panel').first()).toContainText('12:34 PM PHT')
 await p.locator('[data-view="discover"]').click();await p.locator('.card-title').click()
 await expect(p.locator('#detail')).toContainText('12:34 PM PHT')
})
