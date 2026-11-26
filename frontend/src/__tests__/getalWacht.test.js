// @vitest-environment jsdom
// #1254: getallen die de getalcontrole van de server toetst, staan tijdens het streamen niet als cijfers in de DOM,
// maar als "…" met de naam "getal wordt gecontroleerd". Na message_end staan ze er. De regel komt van de server
// (message_start.getalregel, agent/grounding.py); de fixture is die regel, tests/test_getalregel.py houdt hem gelijk.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import axe from 'axe-core'
import REGEL from './fixtures/getalregel.json'
import { useChat } from '../hooks/useChat'
import { Message } from '../components/Message'
import { WACHT_LABEL, regelUit, wachtendeGetallen, zonderStaart } from '../getalWacht'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const gemarkeerd = (tekst, regel = REGEL) => wachtendeGetallen(tekst, regel).map(([b, e]) => tekst.slice(b, e))

describe('welke getallen wachten (de regel van de server)', () => {
  it('een getal van vier of meer cijfers en een percentage', () => {
    expect(gemarkeerd('Er zijn 27.135 studenten, 70,6% slaagt en 1234 blijven.')).toEqual(['27.135', '70,6%', '1234'])
    expect(gemarkeerd('Ruim 12 procent, en 378 490 met een spatie.')).toEqual(['12 procent', '378 490'])
  })

  it('een jaartal, een schooljaar en een getal onder 1.000 niet', () => {
    expect(gemarkeerd('In 2024/25 waren het er 812, in 2023 nog 9,6 per klas.')).toEqual([])
  })

  it('een code niet: 85423NED en T001228 zijn geen getal', () => {
    expect(gemarkeerd('Tabel 85423NED, code T001228.')).toEqual([])
  })

  it('zonder regel van de server wacht elk getal, ook een jaartal', () => {
    expect(gemarkeerd('In 2024 waren het er 812.', null)).toEqual(['2024', '812'])
    expect(regelUit({ type: 'message_start' })).toBeNull()
    expect(regelUit({ type: 'message_start', getalregel: { getal: '(' } })).toBeNull()
    expect(regelUit({ type: 'message_start', getalregel: REGEL })).toBe(REGEL)
  })

  it('het eind van de tekst wacht als het nog een getal kan worden', () => {
    expect(zonderStaart('Er zijn 27.')).toBe('Er zijn ')
    expect(zonderStaart('Er zijn 70,')).toBe('Er zijn ')
    expect(zonderStaart('Er zijn 27.135 studenten.')).toBe('Er zijn 27.135 studenten.')
  })

  it('een percentage waarvan het woord nog binnenkomt, wacht ook ("70,6 pro" en daarna "cent")', () => {
    for (const half of ['p', 'pr', 'pro', 'proc', 'proce', 'procen']) {
      expect(zonderStaart(`Het aandeel is 70,6 ${half}`, REGEL)).toBe('Het aandeel is ')
      expect(zonderStaart(`Het aandeel is 7 ${half}`, REGEL)).toBe('Het aandeel is ')
      expect(zonderStaart(`Het aandeel is 7${half}`, REGEL)).toBe('Het aandeel is ')
    }
    // Een ander woord maakt er geen percentage meer van: dat getal blijft staan, het wacht niet op niets.
    expect(zonderStaart('Er zijn 7 personen', REGEL)).toBe('Er zijn 7 personen')
    expect(zonderStaart('In 2024/25 waren er 812 studenten', REGEL)).toBe('In 2024/25 waren er 812 studenten')
    // Elk teken dat de server kent, telt: een half woord van een ander teken wacht net zo.
    const metPunt = { ...REGEL, procenttekens: [...REGEL.procenttekens, 'pct.'] }
    expect(zonderStaart('Het aandeel is 7 pct', metPunt)).toBe('Het aandeel is ')
  })

  it('zonder de procenttekens van de server wacht elk half woord na een getal', () => {
    const { procenttekens: _, ...oud } = REGEL
    expect(zonderStaart('Het aandeel is 7 pr', oud)).toBe('Het aandeel is ')
    expect(zonderStaart('Er zijn 7 stu', oud)).toBe('Er zijn ')
    expect(zonderStaart('Het aandeel is 7 pr', null)).toBe('Het aandeel is ')
    expect(zonderStaart('Er zijn 27.135 studenten.', oud)).toBe('Er zijn 27.135 studenten.')
  })

  it('een lange reeks cijfers en komma\'s kost geen kwadratische tijd', () => {
    // Hier is de tijd zelf het onderwerp: een patroon dat bij elke positie opnieuw zocht, deed ruim een seconde over
    // deze 60.000 tekens, en dat bij elke render tijdens het streamen.
    const reeks = Array.from({ length: 20000 }, (_, i) => String(i % 10)).join(', ')
    const begin = performance.now()
    expect(zonderStaart(`${reeks}. Meer tekst`, REGEL)).toBe(`${reeks}. Meer tekst`)
    expect(zonderStaart(`${reeks}. Meer tekst`, null)).toBe(`${reeks}. Meer tekst`)
    expect(zonderStaart(`Tekst ${reeks}`, REGEL)).toBe('Tekst ')
    expect(zonderStaart(`Tekst ${reeks} pro`, null)).toBe('Tekst ')
    expect(performance.now() - begin).toBeLessThan(250)
  })

  it('ook in de notatie van het model: de controle leest 9.5% als 9,5% en het Engelse 12,345 als 12.345', () => {
    // agent/controles.py `lezingen`: de stroom is de tekst van het model, de controle toetst wat de gebruiker ziet.
    expect(gemarkeerd('Het aandeel is 9.5% van alle studenten.')).toEqual(['9.5%'])
    expect(gemarkeerd('There are 12,345 students, 1,234.5 on average.')).toEqual(['12,345', '1,234.5'])
    // Een decimaal zonder procent toetst de controle niet, in geen van beide notaties.
    expect(gemarkeerd('Gemiddeld 6.4 per klas, of 9,6.')).toEqual([])
    expect(gemarkeerd('Er zijn 27.135 studenten, 70,6% slaagt.')).toEqual(['27.135', '70,6%'])
  })
})

class FakeWebSocket {
  static OPEN = 1
  static last = null
  constructor() {
    this.readyState = FakeWebSocket.OPEN
    FakeWebSocket.last = this
  }
  send() {}
  close() {}
  emit(event) { this.onmessage({ data: JSON.stringify(event) }) }
}

let root
let container
let chat

beforeEach(async () => {
  globalThis.WebSocket = FakeWebSocket
  // Deltas komen per animatieframe binnen (#510): hier een frame per tik.
  vi.stubGlobal('requestAnimationFrame', cb => setTimeout(cb, 0))
  vi.stubGlobal('cancelAnimationFrame', id => clearTimeout(id))
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  function Harness() {
    chat = useChat()
    return createElement('div', null, chat.messages.map(m => createElement(Message, {
      key: m.id, msg: m, busy: chat.busy, onSend() {}, onClarification() {},
    })))
  }
  await act(async () => { root.render(createElement(Harness)) })
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

async function stuur(...events) {
  await act(async () => {
    for (const ev of events) FakeWebSocket.last.emit(ev)
    await new Promise(r => setTimeout(r, 0))
  })
}

const start = () => stuur({ type: 'message_start', getalregel: REGEL })
const delta = content => stuur({ type: 'text_delta', content })
const einde = content => stuur({ type: 'message_end', content, actions: [], bronnen: [] })
const cijfers = () => container.textContent.replace(/[.\s\u00a0\u202f]/g, '')
const plekken = () => [...container.querySelectorAll('.getal-wacht')]

describe('tijdens het streamen (useChat en Message)', () => {
  it('"27.135" en "70,6%" staan pas na message_end als cijfers in de DOM', async () => {
    await start()
    await delta('Er zijn 27.135 studenten')
    expect(container.textContent).toContain('Er zijn')
    expect(cijfers()).not.toContain('27135')
    await delta(', van wie 70,6% slaagt.')
    expect(cijfers()).not.toContain('27135')
    expect(container.textContent).not.toContain('70,6')
    expect(plekken()).toHaveLength(2)

    await einde('Er zijn 27.135 studenten, van wie 70,6% slaagt.')
    expect(container.textContent).toContain('27.135')
    expect(container.textContent).toContain('70,6%')
    expect(plekken()).toHaveLength(0)
  })

  it('een getal over twee deltas ("27." en "135") staat er geen moment', async () => {
    await start()
    await delta('Er zijn 27.')
    expect(container.textContent).not.toMatch(/\d/)
    await delta('135 studenten.')
    expect(cijfers()).not.toContain('27135')
    expect(container.textContent).not.toMatch(/\b27\b/)
    expect(plekken()).toHaveLength(1)
    await einde('Er zijn 27.135 studenten.')
    expect(container.textContent).toContain('27.135')
  })

  it('"70,6 pro" en daarna "cent": het percentage staat er geen moment als cijfers', async () => {
    await start()
    await delta('Het aandeel is 70,6 pro')
    expect(container.textContent).toContain('Het aandeel is')
    expect(container.textContent).not.toMatch(/\d/)
    await delta('cent, en 7 p')
    expect(container.textContent).not.toMatch(/\d/)
    await delta('rocent twijfelt.')
    expect(container.textContent).not.toMatch(/\d/)
    expect(plekken()).toHaveLength(2)
    await einde('Het aandeel is 70,6 procent, en 7 procent twijfelt.')
    expect(container.textContent).toContain('70,6 procent')
    expect(container.textContent).toContain('7 procent')
  })

  it('9.5% en het Engelse 12,345 staan er tijdens het streamen niet als cijfers', async () => {
    await start()
    await delta('Het aandeel is 9.')
    expect(container.textContent).not.toMatch(/\d/)
    await delta('5% van alle studenten. ')
    expect(container.textContent).not.toMatch(/\d/)
    await delta('In English: there are 12,345 students.')
    expect(container.textContent).not.toMatch(/\d/)
    await einde('Het aandeel is 9,5% van alle studenten. In English: there are 12,345 students.')
    expect(container.textContent).toContain('9,5%')
    expect(container.textContent).toContain('12,345')
  })

  it('een schooljaar en een getal onder 1.000 blijven zichtbaar', async () => {
    await start()
    await delta('In 2024/25 waren het er 812 studenten, ')
    expect(container.textContent).toContain('2024/25')
    expect(container.textContent).toContain('812')
    expect(plekken()).toHaveLength(0)
  })

  it('de plek heeft de naam "getal wordt gecontroleerd" en is bezig', async () => {
    await start()
    await delta('Er zijn 27.135 studenten.')
    const [plek] = plekken()
    expect(plek.getAttribute('role')).toBe('img')
    expect(plek.getAttribute('aria-label')).toBe(WACHT_LABEL)
    expect(plek.getAttribute('aria-busy')).toBe('true')
    expect(plek.textContent).toBe('…')
    // Even breed als het getal: de regel verspringt niet als het verschijnt.
    expect(plek.style.width).toBe('6ch')
  })

  it('ook in een tabel en in vet, maar een code in een codeblok blijft een string', async () => {
    await start()
    await delta('**27.135** studenten\n\n| Jaar | Aantal |\n|---|---|\n| 2024/25 | 28.355 |\n\n`n = 12345`\n\nKlaar.')
    expect(cijfers()).not.toContain('27135')
    expect(cijfers()).not.toContain('28355')
    expect(cijfers()).not.toContain('12345')
    expect(container.textContent).toContain('2024/25')
  })

  it('een eerdere versie die de controle introk, wacht ook zolang het antwoord loopt', async () => {
    await start()
    await delta('Er zijn 27.135 studenten.')
    await stuur({ type: 'message_cancel', reden: ['27.135 staat niet in de opgehaalde data.'] })
    await start()
    await delta('Dat aantal staat niet in de data.')
    expect(cijfers()).not.toContain('27135')
    await einde('Dat aantal staat niet in de data.')
    // Na de controle staat de eerdere versie er weer zoals ze was, dichtgeklapt achter "bekijk de eerdere versie".
    expect(container.querySelector('details.message-ingetrokken').open).toBe(false)
  })

  it('de kopieerknop kopieert wat in beeld staat: zolang de getallen wachten met "…"', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    const kopieer = async () => {
      await act(async () => { container.querySelector('.message.assistant .copy-btn-message').click() })
      return writeText.mock.calls.at(-1)[0]
    }
    await start()
    await delta('Er zijn 27.135 studenten, van wie 70,6 pro')
    const tijdens = await kopieer()
    expect(tijdens).toBe('Er zijn … studenten, van wie ')
    await einde('Er zijn 27.135 studenten, van wie 70,6 procent slaagt.')
    expect(await kopieer()).toBe('Er zijn 27.135 studenten, van wie 70,6 procent slaagt.')
  })

  it('de regel blijft niet aan het bericht hangen na message_end', async () => {
    await start()
    await delta('Tekst.')
    expect(chat.messages.at(-1).getalregel).toEqual(REGEL)
    await einde('Tekst.')
    expect(chat.messages.at(-1).getalregel).toBeUndefined()
  })

  it('axe vindt niets aan de plekken', async () => {
    await start()
    await delta('Er zijn 27.135 studenten, van wie 70,6% slaagt.')
    const { violations } = await axe.run(container, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
      rules: { region: { enabled: false }, 'html-has-lang': { enabled: false } },
    })
    expect(violations.map(v => v.id)).toEqual([])
  })
})
