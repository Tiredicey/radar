import test from 'node:test'
import assert from 'node:assert/strict'
import {amount,safeURL,classify,parseFeed} from '../src/core.js'
const now=new Date('2026-09-18T12:00:00Z')
const rss=(title,date='Fri, 18 Sep 2026 08:00:00 GMT')=>`<rss><channel><item><title>${title}</title><link>https://example.org/grant</link><pubDate>${date}</pubDate><source url="https://example.org">Institution</source></item></channel></rss>`
test('amounts require explicit source evidence',()=>{for(const t of ['DOST JLSS scholarship','CHED TES','Hack4Gov','SCHOLARSHIP 80000'])assert.equal(amount(t).value,0);assert.equal(amount('PHP 2.5 million program budget').value,2500000);assert.equal(amount('P680-K').value,680000)})
test('unsafe links rejected',()=>{for(const u of ['javascript:alert(1)','http://example.org','https://key:secret@example.org'])assert.equal(safeURL(u),'')})
test('classification does not claim a verified opening',()=>{assert.equal(classify('Lipa scholarship applications open').signal,true);assert.equal(classify('Scholarship awarded').signal,false);assert.equal(classify('Batangas grant').local,true)})
test('parser preserves publisher and deterministic identity',async()=>{const [a]=await parseFeed(rss('Scholarship applications open'), 'dost',now);assert.equal(a.publisher,'Institution');assert.equal(a.amount.value,0);assert.equal(a.id,(await parseFeed(rss('Scholarship applications open'),'dost',now))[0].id)})
test('stale missing and future dates excluded',async()=>{for(const d of ['','Mon, 01 Jan 2024 08:00:00 GMT','Thu, 01 Oct 2026 08:00:00 GMT'])assert.equal((await parseFeed(rss('Scholarship',d),'dost',now)).length,0)})
test('invalid and entity-based XML rejected',async()=>{for(const x of ['<html>blocked</html>','<broken>','<!DOCTYPE rss><rss><channel/></rss>'])await assert.rejects(parseFeed(x,'dost',now))})
