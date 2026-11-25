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
