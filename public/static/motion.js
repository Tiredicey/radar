(() => {
  const root = document.documentElement
  const hero = document.querySelector('.hero')
  const radar = document.querySelector('.radar')
  const grid = document.querySelector('#grid')
  const SWEEP = 16
  const EDGE = 135
  const MAX_BLIPS = 36

  hero.classList.add('has-photo')
  hero.insertAdjacentHTML('beforeend', `
    <picture class="hero-photo" aria-hidden="true">
      <source type="image/webp" srcset="/static/hero-960.webp 960w, /static/hero-1600.webp 1600w" sizes="(max-width: 1150px) 100vw, 1200px">
      <img src="/static/hero-1600.webp" alt="" width="1600" height="893" decoding="async" fetchpriority="high">
    </picture>`)
  hero.querySelector(':scope > div').insertAdjacentHTML('beforeend', '<small class="hero-credit">Background: AI-generated illustrative photo, not a real applicant or institution.</small>')
  hero.querySelector('.hero-photo img').addEventListener('error', event => {
    event.currentTarget.closest('.hero-photo').remove()
    hero.classList.remove('has-photo')
  })

  const layer = document.createElement('div')
  layer.className = 'radar-blips'
  radar.append(layer)
  const readout = document.createElement('span')
  readout.className = 'radar-readout'
  radar.append(readout)
  const caption = radar.querySelector('.radar-caption')

  const hash = value => {
    let h = 2166136261
    for (const ch of String(value)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619)
    return (h >>> 0) / 4294967296
  }

  function sweepElapsed() {
    const animation = radar.getAnimations?.({ subtree: true }).find(a => a.animationName === 'radar-sweep')
    const time = Number(animation?.currentTime)
    return Number.isFinite(time) ? (time / 1000) % SWEEP : 0
  }

  function sync() {
    const elapsed = sweepElapsed()
    for (const blip of layer.children) {
      const animation = blip.getAnimations?.()[0]
      if (!animation) continue
      const hit = (((Number(blip.dataset.angle) - EDGE) % 360 + 360) % 360) / 360 * SWEEP
      animation.currentTime = ((((elapsed - hit) % SWEEP) + SWEEP) % SWEEP) * 1000
    }
  }

  function plot(items) {
    const now = Date.now()
    const list = [...items].sort((a, b) => Date.parse(b.published) - Date.parse(a.published)).slice(0, MAX_BLIPS)
    layer.replaceChildren(...list.map(item => {
      const age = Math.min(1, Math.max(0, (now - Date.parse(item.published)) / (30 * 86400000)))
      const angle = Math.round(hash(item.id) * 360)
      const radius = item.local ? 14 + age * 16 : 34 + age * 13
      const rad = (angle - 90) * Math.PI / 180
      const blip = document.createElement('em')
      blip.className = 'radar-blip'
      blip.dataset.kind = item.category
      blip.dataset.local = String(Boolean(item.local))
      blip.dataset.angle = String(angle)
      blip.style.left = `${(50 + Math.cos(rad) * radius).toFixed(2)}%`
      blip.style.top = `${(50 + Math.sin(rad) * radius).toFixed(2)}%`
      return blip
    }))
    const local = list.filter(i => i.local).length
    radar.dataset.plotted = String(list.length)
    readout.textContent = list.length ? `${list.length} lead${list.length === 1 ? '' : 's'} plotted · ${local} near home` : ''
    readout.hidden = !list.length
    if (caption) caption.textContent = list.length ? 'Each dot is one loaded lead. Placement is decorative, not geographic.' : 'Illustration, not a live map'
    requestAnimationFrame(sync)
  }

  document.addEventListener('radar:data', event => { if (event.detail.loaded) plot(event.detail.items) })
  if (typeof state !== 'undefined' && state.loaded) plot(state.items)
  new MutationObserver(() => requestAnimationFrame(sync)).observe(root, { attributes: true, attributeFilter: ['data-motion'] })

  const seen = new Set()
  new MutationObserver(() => {
    let index = 0
    for (const card of grid.querySelectorAll('.card')) {
      const id = card.querySelector('[data-detail]')?.dataset.detail
      if (!id || seen.has(id)) continue
      seen.add(id)
      card.classList.add('card-enter')
      card.style.setProperty('--stagger', String(Math.min(index++, 11)))
      card.addEventListener('animationend', () => card.classList.remove('card-enter'), { once: true })
    }
  }).observe(grid, { childList: true })

  const values = new Map()
  for (const stat of document.querySelectorAll('.stats strong')) {
    values.set(stat, stat.textContent)
    new MutationObserver(() => {
      if (values.get(stat) === stat.textContent) return
      values.set(stat, stat.textContent)
      if (!/^\d/.test(stat.textContent)) return
      stat.classList.remove('stat-changed')
      void stat.offsetWidth
      stat.classList.add('stat-changed')
    }).observe(stat, { childList: true, characterData: true, subtree: true })
  }

  if ('IntersectionObserver' in window) {
    const targets = document.querySelectorAll('.stats article, .panel, .visual-guide, .research-grid > *')
    const reveal = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        entry.target.classList.add('revealed')
        reveal.unobserve(entry.target)
      }
    }, { rootMargin: '0px 0px -8% 0px' })
    root.classList.add('reveal-ready')
    targets.forEach(el => { el.classList.add('reveal'); reveal.observe(el) })
  }
})()
