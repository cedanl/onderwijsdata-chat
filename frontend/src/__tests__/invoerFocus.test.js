// @vitest-environment jsdom
// #584: op een telefoon verdween de tabbalk (#527) meteen bij focus in het invoerveld en kwam hij meteen terug
// bij blur. Een tik op 'Verstuur bericht' verplaatst de focus bij mousedown; de layout sprong 58 px, de mouseup
// landde op de disclaimer en de klik kwam niet aan. De wissel volgt nu pas na de lopende tik.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { volgInvoerFocus, INVOER_ACTIEF } from '../invoerFocus'

const actief = () => document.body.classList.contains(INVOER_ACTIEF)
const pointer = (el, type) => el.dispatchEvent(new Event(type, { bubbles: true }))

describe('volgInvoerFocus', () => {
  let stop, veld, knop
  beforeEach(() => {
    vi.useFakeTimers()
    document.body.innerHTML = '<textarea class="chat-input"></textarea><button class="send-btn">Verstuur</button><a href="#x">elders</a>'
    veld = document.querySelector('.chat-input')
    knop = document.querySelector('.send-btn')
    stop = volgInvoerFocus(document)
  })
  afterEach(() => {
    stop()
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('markeert de focus in het invoerveld, maar pas na de lopende gebeurtenis', () => {
    veld.focus()
    expect(actief()).toBe(false)
    vi.runAllTimers()
    expect(actief()).toBe(true)
  })

  it('haalt de markering weg als de focus het veld verlaat, ook pas daarna', () => {
    veld.focus()
    vi.runAllTimers()
    knop.focus()
    expect(actief()).toBe(true)
    vi.runAllTimers()
    expect(actief()).toBe(false)
  })

  it('wisselt niet zolang er een vinger of muisknop is ingedrukt', () => {
    veld.focus()
    vi.runAllTimers()
    pointer(knop, 'pointerdown')
    knop.focus()
    vi.runAllTimers()
    expect(actief()).toBe(true)
    pointer(knop, 'pointerup')
    expect(actief()).toBe(true)
    vi.runAllTimers()
    expect(actief()).toBe(false)
  })

  it('wisselt ook na een afgebroken aanraking', () => {
    veld.focus()
    vi.runAllTimers()
    pointer(knop, 'pointerdown')
    knop.focus()
    pointer(knop, 'pointercancel')
    vi.runAllTimers()
    expect(actief()).toBe(false)
  })

  it('ziet een veld dat al focus had bij de start', () => {
    stop()
    veld.focus()
    stop = volgInvoerFocus(document)
    vi.runAllTimers()
    expect(actief()).toBe(true)
  })

  it('stopt met volgen en laat geen markering achter', () => {
    veld.focus()
    vi.runAllTimers()
    stop()
    expect(actief()).toBe(false)
    knop.focus()
    veld.focus()
    vi.runAllTimers()
    expect(actief()).toBe(false)
  })
})

describe('tabbalk met het toetsenbord open (#527, #584)', () => {
  const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
  const touch = css.slice(css.indexOf('@media (pointer: coarse) and (max-width: 1024px)'))

  it('verbergt de tabbalk op de markering van invoerFocus.js, op touch', () => {
    expect(touch).toMatch(/^@media \(pointer: coarse\) and \(max-width: 1024px\) \{\s*body\.invoer-actief \{ --mobile-tabs-h: 0px; \}\s*body\.invoer-actief \.mobile-tabs \{ display: none; \}/)
  })

  it('reageert niet meer direct op :focus van het invoerveld', () => {
    expect(css).not.toContain('.chat-input:focus)')
  })
})
