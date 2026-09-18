import { XMLParser, XMLValidator } from 'fast-xml-parser'
export function safeURL(value) {
  try { const u=new URL(value); return u.protocol==='https:'&&!u.username&&!u.password?u.href:'' } catch { return '' }
}
export function amount(text) {
  const m=/(?:₱|\bPHP\b|\bP(?=\s*\d))\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:-?\s*(thousand|million|billion|[kmb])\b)?/i.exec(text)
  if(!m)return {value:0,evidence:''}
  const value=Math.round(Number(m[1].replaceAll(',',''))*({k:1e3,thousand:1e3,m:1e6,million:1e6,b:1e9,billion:1e9}[m[2]?.toLowerCase()]||1))
  return {value:Number.isSafeInteger(value)?value:0,evidence:m[0].trim()}
}
export function relevant(text) {
  return /\b(scholarships?|scholars|students?|educational assistance|tuition|stipend|hackathon|hack4gov|bounty|startup)\b|research.{0,30}(?:grant|fund)|grant.{0,30}research/i.test(text)
}
export function classify(text) {
  return {category:/hackathon|hack4gov|bounty|startup challenge|competition/i.test(text)?'competitions':/scholarship|jlss|scholars/i.test(text)?'scholarships':'grants',local:/\b(lipa|batangas|calabarzon|region (4a|iv-a)|southern tagalog)\b/i.test(text),signal:! /\b(closed|awarded|graduates|deadline passed)\b/i.test(text)&&/\b(apply|applications? (are |is )?(open|until|deadline)|accepting applications|call for (applications|proposals))\b/i.test(text)}
}
export function text(value) {
  return typeof value==='string'?value.replace(/<[^>]*>/g,' ').replace(/&(?:nbsp|amp|lt|gt|quot|apos);/g,v=>({'&nbsp;':' ','&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&apos;':"'"})[v]).replace(/\s+/g,' ').trim():''
}
export async function parseFeed(xml,source,now=new Date()) {
  if(xml.length>1500000||/<!DOCTYPE|<!ENTITY/i.test(xml)||XMLValidator.validate(xml)!==true)throw new Error('Invalid RSS')
  const data=new XMLParser({ignoreAttributes:false,parseTagValue:false,processEntities:false}).parse(xml)
  if(!data.rss?.channel)throw new Error('RSS channel missing')
  const raw=data.rss.channel.item||[],out=[]
  for(const item of (Array.isArray(raw)?raw:[raw]).slice(0,100)) {
    const title=text(item.title).slice(0,500),summary=text(item.description).slice(0,2000),link=safeURL(item.link),published=Date.parse(item.pubDate),full=title+' '+summary
    if(!title||!link||!Number.isFinite(published)||published<now.getTime()-30*86400000||published>now.getTime()+86400000)continue
    if(!relevant(full)||/minimum (spend|purchase)|checkout promo|application fee|processing fee|guaranteed income|deposit to claim/i.test(full))continue
    const publisher_url=safeURL(item.source?.['@_url'])
    const blocked=['picodi.com','iprice.ph','couponbirds.com','retailmenot.com']
    if([link,publisher_url].filter(Boolean).some(u=>blocked.some(d=>new URL(u).hostname===d||new URL(u).hostname.endsWith('.'+d))))continue
    const id=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(title.toLowerCase()+'|'+link))),b=>b.toString(16).padStart(2,'0')).join('').slice(0,16)
    out.push({id,title,summary,link,source,publisher:text(item.source?.['#text']||item.source)||'Publisher not supplied',publisher_url,published:new Date(published).toISOString(),collected:now.toISOString(),amount:amount(full),...classify(full)})
  }
  return out
}
