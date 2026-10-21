// @vitest-environment jsdom
// #649: op een telefoon verschoof de pagina rond de eerste vraag drie keer (CLS 0,27): de verbindingsregel bij het
// laden, elke regel van een lange vraag, en het leegmaken bij versturen (de composer sprong 76 px). Het invoerkader
// heeft nu een vaste plek van één regel en groeit daarboven over de berichten. jsdom rekent geen layout, dus de CSS
// ligt hier vast; tests/e2e/mobiel-welkom-cls.spec.js meet het in de browser.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import Composer from '../components/Composer'
import ChatNavActies from '../components/ChatNavActies'
import { NavSlotContext } from '../navSlot'
import { MAX_MESSAGE_CHARS } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')

// Top-level rules and @media blocks in file order: { media, selectors, body }.
function parseRules(text, media = null) {
  const rules = []
  let i = 0
  while (i < text.length) {
    const open = text.indexOf('{', i)
    if (open === -1) break
    const prelude = text.slice(i, open).trim()
    let depth = 1
    let j = open + 1
    while (depth > 0 && j < text.length) {
      if (text[j] === '{') depth++
      else if (text[j] === '}') depth--
      j++
    }
    const inner = text.slice(open + 1, j - 1)
    if (prelude.startsWith('@media')) rules.push(...parseRules(inner, prelude))
    else if (!prelude.startsWith('@')) rules.push({ media, selectors: prelude.split(',').map(s => s.trim()), body: inner })
    i = j
  }
  return rules
}

const rules = parseRules(css)
const COMPACT = '@media (max-width: 1024px)'
const rule = (selector, media) => rules.filter(r => r.media === media && r.selectors.includes(selector))
const decl = (body, prop) => body.match(new RegExp(`(?:^|[;\\s])${prop}:\\s*([^;]+?)\\s*(?:;|$)`))?.[1]
const declOf = (selector, media, prop) => rule(selector, media).map(r => decl(r.body, prop)).filter(Boolean).at(-1)

const PROPS = {
  hasMessages: false, connected: true, busy: false, models: [], selectedModel: '', onModelChange: () => {},
  onStop: () => {}, onSubmit: () => true, max: MAX_MESSAGE_CHARS, rejectedDraft: null, clearRejectedDraft: () => {},
}

let root
let container

async function render(element, host = document.body) {
  container = document.createElement('div')
  host.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  document.body.innerHTML = ''
  root = null
  vi.restoreAllMocks()
  delete globalThis.ResizeObserver
})

describe('het invoerkader in een vaste plek', () => {
  it('zet de pil in een eigen plek: dat is de root van de Composer', async () => {
    await render(createElement(Composer, PROPS))
    const slot = container.firstElementChild
    expect(slot.className).toBe('chat-input-slot')
    expect([...slot.children].map(c => c.className)).toEqual(['chat-input-wrap'])
  })

  it('laat de plek op desktop geen eigen vak hebben', () => {
    expect(declOf('.chat-input-slot', null, 'display')).toBe('contents')
  })

  it('geeft de plek op een telefoon een vaste hoogte van één regel, afgeleid van --tap-min', () => {
    expect(declOf('.chat-input-slot', COMPACT, 'position')).toBe('relative')
    expect(declOf('.chat-input-slot', COMPACT, 'display')).toBe('block')
    expect(declOf('.chat-input-slot', COMPACT, 'height')).toBeUndefined()
    // De hoogte komt van een leeg blok: de verstuurknop plus de padding van de pil, en een rand zo dik als die van de
    // pil, zodat de browser hem op dezelfde manier afrondt.
    const regel = '.chat-input-slot::before'
    expect(declOf(regel, COMPACT, 'display')).toBe('block')
    expect(declOf(regel, COMPACT, 'box-sizing')).toBe('content-box')
    expect(declOf(regel, COMPACT, 'height')).toBe('calc(var(--tap-min) + 2 * 4px)')
    expect(declOf('.chat-input-wrap', COMPACT, 'padding')).toMatch(/^4px \S+ 4px /)
    const randPil = declOf('.chat-input-wrap', null, 'border').split(' ')[0]
    expect(declOf(regel, COMPACT, 'border-block')).toBe(`${randPil} solid transparent`)
    // En de verstuurknop, die de regel zijn hoogte geeft, volgt hetzelfde token.
    expect(declOf('.send-btn', COMPACT, 'height')).toBe('var(--tap-min)')
  })

  it('laat de pil op een telefoon vanaf de onderkant van zijn plek omhoog groeien, boven de scrollknop', () => {
    const pil = '.chat-input-slot > .chat-input-wrap'
    expect(declOf(pil, COMPACT, 'position')).toBe('absolute')
    for (const kant of ['left', 'right', 'bottom']) expect(declOf(pil, COMPACT, kant), kant).toBe('0')
    expect(declOf(pil, COMPACT, 'top')).toBeUndefined()
    // .scroll-to-bottom-btn heeft z-index 10.
    expect(Number(declOf(pil, COMPACT, 'z-index'))).toBeGreaterThan(10)
  })

  it('reserveert de hoogte op de plek, niet op het invoergebied: banners en voortgang erboven blijven in de flow', () => {
    for (const media of [null, COMPACT]) {
      expect(declOf('.chat-input-area', media, 'height'), String(media)).toBeUndefined()
      expect(declOf('.chat-input-area', media, 'min-height'), String(media)).toBeUndefined()
    }
  })

  it('geeft de berichten de uitstekende hoogte als ruimte aan hun eind, alleen als er berichten zijn', () => {
    expect(declOf('.chat-main:has(.message) .chat-messages', COMPACT, 'margin-bottom')).toBe('var(--composer-extra, 0px)')
    // Op het welkomstscherm zou die ruimte de centrering weer verschuiven.
    const zonderBerichten = rules.filter(r => r.body.includes('--composer-extra') &&
      r.selectors.some(s => s.includes('.chat-messages') && !s.includes(':has(.message)')))
    expect(zonderBerichten).toEqual([])
  })

  it('schuift banners en voortgang boven het invoerkader mee omhoog, de pil zelf niet', () => {
    const erboven = '.chat-input-area > :not(.chat-input-slot)'
    expect(declOf(erboven, COMPACT, 'position')).toBe('relative')
    expect(declOf(erboven, COMPACT, 'top')).toBe('calc(-1 * var(--composer-extra, 0px))')
  })

  it('zet de verbindingsmelding op een telefoon boven de pil, ondoorzichtig en onder de melding bij versturen', () => {
    const ws = '.chat-input-footer .ws-reconnecting:not(:empty)'
    expect(declOf(ws, COMPACT, 'position')).toBe('absolute')
    expect(declOf(ws, COMPACT, 'bottom')).toBe('calc(100% + 6px)')
    expect(declOf(ws, COMPACT, 'background')).toBe('var(--white)')
    expect(Number(declOf(ws, COMPACT, 'z-index'))).toBeLessThan(Number(declOf('.send-notice', null, 'z-index')))
    // Desktop houdt de melding links in de voet.
    expect(rules.filter(r => r.media === null && r.selectors.some(s => s.includes('.ws-reconnecting:not(:empty)')))).toEqual([])
  })
})

describe('de Composer meldt wat de pil boven zijn plek uitsteekt', () => {
  let hoogte
  let observers

  // Een pil van 133 px in een plek van 55 px (de getallen doen er niet toe, het verschil wel).
  function nepLayout() {
    hoogte = { 'chat-input-slot': 55, 'chat-input-wrap': 133 }
    observers = []
    globalThis.ResizeObserver = class {
      constructor(callback) { this.callback = callback; this.elementen = []; observers.push(this) }
      observe(el) { this.elementen.push(el) }
      disconnect() { this.elementen = [] }
    }
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function () {
      const h = hoogte[this.className] ?? 0
      return { top: 0, left: 0, right: 0, bottom: h, width: 0, height: h, x: 0, y: 0 }
    })
  }

  async function renderInChat(props) {
    const chat = document.createElement('div')
    chat.className = 'chat-main'
    document.body.appendChild(chat)
    await render(createElement(Composer, { ...PROPS, ...props }), chat)
    return chat
  }

  it('zet --composer-extra op de chat en volgt de hoogte van de pil', async () => {
    nepLayout()
    const chat = await renderInChat({ compact: true })
    expect(chat.style.getPropertyValue('--composer-extra')).toBe('78px')
    const pil = container.querySelector('.chat-input-wrap')
    expect(observers.flatMap(o => o.elementen)).toContain(pil)

    hoogte['chat-input-wrap'] = 55
    await act(async () => observers.forEach(o => o.callback([])))
    expect(chat.style.getPropertyValue('--composer-extra')).toBe('0px')

    await act(async () => root.unmount())
    root = null
    expect(chat.style.getPropertyValue('--composer-extra')).toBe('')
    expect(observers.flatMap(o => o.elementen)).toEqual([])
  })

  it('meldt een hoogte die de Composer zelf zet meteen, zonder op de observer te wachten', async () => {
    nepLayout()
    const onSubmit = vi.fn(() => true)
    const chat = await renderInChat({ compact: true, onSubmit })
    const veld = container.querySelector('textarea.chat-input')
    hoogte['chat-input-wrap'] = 109
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(veld, 'Een lange vraag')
      veld.dispatchEvent(new Event('input', { bubbles: true }))
    })
    expect(chat.style.getPropertyValue('--composer-extra')).toBe('54px')

    // Versturen maakt het veld leeg: de ruimte erboven is in dezelfde taak weg, niet een frame later.
    hoogte['chat-input-wrap'] = 55
    await act(async () => container.querySelector('.send-btn').click())
    expect(onSubmit).toHaveBeenCalledWith('Een lange vraag')
    expect(chat.style.getPropertyValue('--composer-extra')).toBe('0px')
  })

  it('meldt niets op desktop: daar staat de pil gewoon in de flow', async () => {
    nepLayout()
    const chat = await renderInChat({ compact: false })
    expect(chat.style.getPropertyValue('--composer-extra')).toBe('')
    expect(observers).toEqual([])
  })

  it('werkt zonder ResizeObserver, zoals in oudere browsers', async () => {
    const chat = await renderInChat({ compact: true })
    expect(chat.style.getPropertyValue('--composer-extra')).toBe('')
    expect(container.querySelector('textarea.chat-input')).not.toBeNull()
  })
})

describe('een vaste plek voor het ⋯-menu in de navbar', () => {
  async function renderNav(exportMessages) {
    const slot = document.createElement('div')
    slot.className = 'navbar-pagina'
    document.body.appendChild(slot)
    await render(createElement(NavSlotContext.Provider, { value: slot },
      createElement(ChatNavActies, { sidebarOpen: false, onToggleSidebar: () => {}, exportMessages })))
    return slot
  }

  it('houdt zonder gesprek een lege, verborgen plek vrij, zonder knop en zonder tabstop', async () => {
    const slot = await renderNav(null)
    expect(slot.querySelector('button[aria-label="Meer acties"]')).toBeNull()
    const leeg = slot.querySelector('.navbar-icon-slot')
    expect(leeg).not.toBeNull()
    expect(leeg.getAttribute('aria-hidden')).toBe('true')
    expect(leeg.childElementCount).toBe(0)
    expect(leeg.matches('button, a, [tabindex]')).toBe(false)
    expect([...slot.children].map(c => c.className)).toEqual(['navbar-icon-btn', 'navbar-icon-slot'])
  })

  it('zet de ⋯-knop op die plek zodra er een gesprek is', async () => {
    const slot = await renderNav([{ id: 1, role: 'user', content: 'Hoeveel mbo-studenten?', done: true }])
    expect(slot.querySelector('button[aria-label="Meer acties"]')).not.toBeNull()
    expect(slot.querySelector('.navbar-icon-slot')).toBeNull()
  })

  it('maakt de plek op een telefoon even breed als de knop', () => {
    expect(declOf('.navbar-icon-slot', COMPACT, 'width')).toBe('var(--tap-min)')
    expect(declOf('.navbar-icon-slot', COMPACT, 'flex-shrink')).toBe('0')
  })
})
