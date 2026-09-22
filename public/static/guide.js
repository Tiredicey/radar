(() => {
  const find = selector => document.querySelector(selector)
  const actions = document.createElement('div')
  actions.className = 'hero-actions'
  find('#local-button').before(actions)
  actions.append(find('#local-button'))
  actions.insertAdjacentHTML('beforeend', '<button class="button watch-guide" data-open-guide><span aria-hidden="true">▷</span> Watch the research guide</button>')
  find('#guide').insertAdjacentHTML('afterbegin', `
    <section class="visual-guide" aria-labelledby="visual-guide-title">
      <button class="guide-preview" data-open-guide aria-label="Open the animated research guide">
        <img src="/static/research-guide.webp" width="960" height="540" loading="lazy" decoding="async" alt="Illustrated research path: discover a lead, read its source, verify with the institution">
        <span class="play-label"><span aria-hidden="true">▷</span> Watch guide · 18 sec</span>
      </button>
      <div><p class="eyebrow">A CLEARER NEXT STEP</p><h2 id="visual-guide-title">From a headline<br>to an informed decision.</h2>
        <p>A short, silent visual guide to researching a lead. No promises of eligibility or awards.</p>
        <button class="button" data-open-guide>Open video &amp; transcript</button>
        <p class="media-credit">Original Radar illustration and animation. Conceptual, not an institution endorsement.</p>
      </div>
    </section>`)
  document.body.insertAdjacentHTML('beforeend', `
    <dialog id="guide-dialog" aria-labelledby="guide-dialog-title">
      <button class="close" id="guide-close" aria-label="Close research guide" autofocus>×</button>
      <p class="eyebrow">RESEARCH WITH CONTEXT</p><h2 id="guide-dialog-title">A lead is only the beginning.</h2>
      <p>18-second silent animation. Press Play to watch, or read the complete text below.</p>
      <video id="research-video" controls playsinline preload="none" poster="/static/research-guide.webp" width="960" height="540" aria-label="Research a funding lead: animated guide" aria-describedby="guide-transcript">
        <source src="/static/research-guide.webm" type="video/webm"><source src="/static/research-guide.mp4" type="video/mp4">
        <track kind="captions" src="/static/research-guide.vtt" srclang="en" label="English">
        Your browser cannot play this video. Read the guide below.
      </video>
      <p id="video-status" role="status" hidden></p>
      <section id="guide-transcript"><h3>The guide, in words</h3><ol>
        <li><strong>Discover a lead.</strong> Search by keyword, category or location. A match is a research lead, not a verified open application.</li>
        <li><strong>Read the source.</strong> Check the publisher and publication date. An amount may be a program budget, not your payout.</li>
        <li><strong>Verify before applying.</strong> Confirm the current deadline, eligibility and fees with the institution. Use official channels before sharing documents.</li>
      </ol></section><p class="media-credit">Original Radar motion graphic. No audio or third-party tracking.</p>
    </dialog>`)
  const dialog = find('#guide-dialog')
  const video = find('#research-video')
  const status = find('#video-status')
  const failedSources = new Set()
  const reduced = matchMedia('(prefers-reduced-motion: reduce)')
  let opener = null
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-open-guide]')
    if (!button) return
    opener = button
    if (!dialog.open) dialog.showModal()
  })
  find('#guide-close').addEventListener('click', () => { video.pause(); dialog.close() })
  dialog.addEventListener('cancel', () => video.pause())
  dialog.addEventListener('close', () => {
    video.pause()
    if (opener?.isConnected && opener.getClientRects().length) opener.focus()
  })
  reduced.addEventListener('change', () => { if (reduced.matches) video.pause() })
  find('#motion-toggle').addEventListener('click', () => {
    if (document.documentElement.dataset.motion === 'paused') video.pause()
  })
  document.addEventListener('visibilitychange', () => { if (document.hidden) video.pause() })
  function mediaFailed() {
    status.textContent = 'Video unavailable. The complete guide is available below.'
    status.hidden = false
  }
  video.addEventListener('error', mediaFailed)
  video.querySelectorAll('source').forEach(source => source.addEventListener('error', () => {
    failedSources.add(source)
    if (failedSources.size === video.querySelectorAll('source').length) mediaFailed()
  }))
  video.addEventListener('loadstart', () => { failedSources.clear(); status.hidden = true })
  video.addEventListener('playing', () => { status.textContent = ''; status.hidden = true })
  find('.guide-preview img').addEventListener('error', event => {
    event.currentTarget.hidden = true
    find('.guide-preview').classList.add('image-unavailable')
  })
})()
