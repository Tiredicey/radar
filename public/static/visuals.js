(() => {
  const controls = document.createElement('div')
  controls.className = 'workspace-controls'
  controls.innerHTML = '<button id="focus-mode" aria-pressed="false">Focus mode</button><button id="motion-toggle" aria-pressed="false">Pause motion</button>'
  controls.append(document.querySelector('#theme'))
  document.querySelector('header').append(controls)
  document.querySelector('.radar').insertAdjacentHTML('beforeend', '<em class="radar-point radar-point-one"></em><em class="radar-point radar-point-two"></em><em class="radar-point radar-point-three"></em><span class="radar-caption">Illustration, not a live map</span>')
  const motion = document.querySelector('#motion-toggle')
  const focus = document.querySelector('#focus-mode')
  const reduced = matchMedia('(prefers-reduced-motion: reduce)')
  let paused = false
  function update() {
    const stopped = paused || reduced.matches
    document.documentElement.dataset.motion = stopped ? 'paused' : 'on'
    motion.setAttribute('aria-pressed', String(stopped))
    motion.textContent = reduced.matches ? 'Reduced motion' : paused ? 'Resume motion' : 'Pause motion'
    motion.disabled = reduced.matches
    motion.title = reduced.matches ? 'Following your device reduced-motion preference' : 'Control decorative interface animation'
  }
  motion.addEventListener('click', () => { paused = !paused; update() })
  reduced.addEventListener('change', update)
  update()
  focus.addEventListener('click', () => {
    const active = focus.getAttribute('aria-pressed') !== 'true'
    focus.setAttribute('aria-pressed', String(active))
    document.body.dataset.focus = String(active)
    focus.textContent = active ? 'Exit focus mode' : 'Focus mode'
  })
  document.addEventListener('visibilitychange', () => {
    document.documentElement.dataset.pageHidden = String(document.hidden)
  })
})()
