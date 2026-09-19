(()=>{
 const root=document.querySelector('#legal'),find=s=>root.querySelector(s)
 const handbook='https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/46/63230',constitution='https://lawphil.net/consti/cons1987.html'
 const sources=[['Supreme Court E-Library','elibrary.judiciary.gov.ph','https://elibrary.judiciary.gov.ph/','Official judiciary source'],['Supreme Court','sc.judiciary.gov.ph','https://sc.judiciary.gov.ph/','Official judiciary source'],['Lawphil','lawphil.net','https://lawphil.net/','Nonofficial reference'],['ChanRobles','chanrobles.com','https://www.chanrobles.com/','Nonofficial reference']]
 const terms=[
  ['Due process','Article III, Section 1 protects against deprivation of life, liberty or property without due process of law. Research the procedures and standards relevant to the particular dispute.',constitution,'1987 Constitution, Article III, Section 1'],
  ['Equal protection','Article III, Section 1 prohibits denial of the equal protection of the laws. The clause is a starting point for research, not a determination that a particular distinction is unconstitutional.',constitution,'1987 Constitution, Article III, Section 1'],
  ['Grave abuse of discretion','Article VIII, Section 1 includes judicial review of grave abuse of discretion amounting to lack or excess of jurisdiction by a government branch or instrumentality. Research the applicable judicial standard and remedy before applying this ground to particular facts.',constitution,'1987 Constitution, Article VIII, Section 1, paragraph 2'],
  ['Ratio decidendi','The reason or principle underlying a court decision. Connect the reasoning to the material facts and issues the court resolved.',handbook,'Fundamentals of Decision Writing for Judges, Chapter Three: Ratio Decidendi','A Latin term which refers to the underlying reason or principle which justifies a court decision.'],
  ['Obiter dictum','A statement made in passing that is unnecessary to decide the issues before the court. Distinguish it from the reasoning needed for the decision.',handbook,'Fundamentals of Decision Writing for Judges, Chapter Three: Obiter Dictum','A Latin term which refers to an averment, assertion, or observation stated as an aside or a “by the way,” or said in passing by a court that is not necessary in deciding the issues before the court.'],
  ['Dispositive portion','The part of the decision stating the judgment or resolution of the issues. Also look for the term fallo. Read it alongside the reasoning and any later resolution.',handbook,'Fundamentals of Decision Writing for Judges, Chapter Three: Dispositive Portion','That part of a court decision which contains the judgment or resolution of the issues subject of the complaint or petition.']
 ]
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n}
 const link=(text,url)=>{const n=el('a',text);n.href=url;n.target='_blank';n.rel='noopener noreferrer';return n}
 function search(){
  const q=find('#legal-query').value.trim(),exact=find('#legal-exact').checked
  find('#legal-links').replaceChildren(...sources.map(([name,domain,home,kind])=>{
   const card=el('article',null,'panel'),url=new URL('https://www.google.com/search')
   url.searchParams.set('as_sitesearch',domain);url.searchParams.set(exact?'as_epq':'as_q',q)
   card.append(el('small',kind),el('h3',name),link('Open source website',home))
   if(q){const a=link('Search this source via Google',url.href);a.className='button';card.append(a)}
   return card
  }))
  find('#legal-status').textContent=q?'Search links prepared. Choose a source; results open on Google.':'Enter a topic or phrase to prepare source-specific search links.'
 }
 function glossary(){
  const q=find('#legal-filter').value.trim().toLowerCase(),filtered=terms.filter(t=>(t[0]+' '+t[1]).toLowerCase().includes(q))
  find('#legal-terms').replaceChildren(...filtered.map(([name,text,url,cite,quote])=>{
   const card=el('article',null,'panel'),details=el('details'),button=el('button','Research this term','button')
   card.append(el('h3',name),el('small','Learning explanation, not a quotation'),el('p',text));details.append(el('summary','Source and context'))
   if(quote)details.append(el('p','Source excerpt'),el('blockquote',quote))
   details.append(link(cite,url),el('p',url===handbook?'Official E-Library educational handbook; not itself a judicial holding.':'Constitution text hosted by Lawphil, a nonofficial reference.'),el('p','Source checked 19 September 2026. Subsequent treatment and current controlling status have not been checked.'))
   button.type='button';button.addEventListener('click',()=>{find('#legal-query').value=name;search();find('#legal-query').focus()});card.append(details,button);return card
  }))
  find('#legal-count').textContent=filtered.length?filtered.length+' learning entries shown.':'No matching learning entries. This is a small glossary, not a complete legal index.'
 }
 find('#legal-form').addEventListener('submit',e=>{e.preventDefault();search()})
 find('#legal-query').addEventListener('input',search);find('#legal-exact').addEventListener('change',search);find('#legal-filter').addEventListener('input',glossary)
 find('#legal-clear').addEventListener('click',()=>{find('#legal-query').value='';find('#legal-filter').value='';find('#legal-exact').checked=false;search();glossary();find('#legal-query').focus()})
 search();glossary()
})()
