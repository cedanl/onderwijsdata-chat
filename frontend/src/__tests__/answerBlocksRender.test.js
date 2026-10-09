// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import { Message } from '../pages/ChatPage'
import { ALLEEN_CITATIES, CBS, DUO, VIJF_ANTWOORDEN } from './fixtures/vijfAntwoorden'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let mounted = []

afterEach(() => {
  for (const { root, container } of mounted) {
    act(() => root.unmount())
    container.remove()
  }
  mounted = []
})

function render(msg, props = {}) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  mounted.push({ root, container })
  act(() => root.render(createElement(Message, { msg, ...props })))
  return container
}

const blokken = el => [...el.querySelectorAll('[data-blok]')]
const blok = (el, kind) => el.querySelector(`[data-blok="${kind}"]`)

// CH-09 (#416): vijf keer dezelfde vraag, nu vijf keer dezelfde rijen onder het antwoord.
describe('vaste bouwstenen onder een dataantwoord', () => {
  it('staan bij vijf runs van dezelfde vraag in dezelfde volgorde', () => {
    const volgordes = VIJF_ANTWOORDEN.map(msg => blokken(render(msg)).map(b => b.dataset.blok).join(' · '))
    expect(new Set(volgordes)).toEqual(new Set(['citaties · telling · export · bronnen']))
  })

  it('zijn bij elke run gevuld met wat er is, of n.v.t.', () => {
    for (const msg of VIJF_ANTWOORDEN) {
      const el = render(msg)
      for (const b of blokken(el)) {
        const dd = b.querySelector('dd')
        if (b.dataset.status === 'n.v.t.') {
          expect(dd.textContent).toBe('n.v.t.')
          continue
        }
        expect(b.dataset.status).toBe('aanwezig')
        const gevuld = {
          citaties: () => expect(dd.textContent).toMatch(/^9 getallen/),
          telling: () => expect(dd.querySelector('details.telling')).not.toBeNull(),
          export: () => expect(dd.querySelectorAll('.data-export-btn')).toHaveLength(msg.tools.length),
          bronnen: () => expect(dd.querySelectorAll('li')).toHaveLength(msg.bronnen.length),
        }
        gevuld[b.dataset.blok]()
      }
    }
  })

  it('geven elk blok een status, en n.v.t. letterlijk als het leeg is', () => {
    const el = render(ALLEEN_CITATIES)
    expect(blokken(el).map(b => [b.dataset.blok, b.dataset.status])).toEqual([
      ['citaties', 'aanwezig'], ['telling', 'n.v.t.'], ['export', 'n.v.t.'], ['bronnen', 'n.v.t.'],
    ])
    for (const kind of ['telling', 'export', 'bronnen']) {
      expect(blok(el, kind).querySelector('dd').textContent).toBe('n.v.t.')
    }
  })

  it('tonen het aantal citaties en hoeveel daarvan geen vastgestelde herkomst hebben', () => {
    const el = render(VIJF_ANTWOORDEN[1])
    expect(blok(el, 'citaties').querySelector('dd').textContent).toBe('9 getallen, waarvan 2 zonder vastgestelde herkomst')
    const zonder = render(VIJF_ANTWOORDEN[0])
    expect(blok(zonder, 'citaties').dataset.status).toBe('n.v.t.')
  })

  it('zetten de bestaande Telling, CSV-knoppen en de bronnenlijst in hun blok', () => {
    const el = render(VIJF_ANTWOORDEN[1])
    const telling = blok(el, 'telling').querySelector('details.telling')
    expect(telling).not.toBeNull()
    expect(telling.querySelector('summary').textContent).toBe('Ingeschrevenen: hoofdinschrijvingen op 1 oktober.')
    expect(blok(el, 'export').querySelectorAll('.data-export-btn')).toHaveLength(4)
    expect([...blok(el, 'bronnen').querySelectorAll('li')].map(li => li.textContent)).toEqual([DUO, CBS])
  })

  it('tonen de Telling en de CSV-knoppen niet ook nog buiten de blokken', () => {
    const el = render(VIJF_ANTWOORDEN[1])
    expect(el.querySelectorAll('details.telling')).toHaveLength(1)
    expect(el.querySelectorAll('.data-export')).toHaveLength(1)
    expect(el.querySelector('.answer-blocks details.telling')).not.toBeNull()
    expect(el.querySelector('.message-bubble').textContent).not.toContain('**Telling**')
  })
})

describe('geen dataantwoord: zoals het was', () => {
  const [, data] = VIJF_ANTWOORDEN

  it('een bericht van vóór de bronnenlijst houdt zijn Telling in de tekst en losse CSV-knoppen', () => {
    const { bronnen: _weg, ...oud } = data
    const el = render(oud)
    expect(blokken(el)).toHaveLength(0)
    expect(el.querySelector('details.telling summary').textContent).toBe(
      'Telling Ingeschrevenen: hoofdinschrijvingen op 1 oktober.',
    )
    expect(el.querySelectorAll('.data-export-btn')).toHaveLength(4)
  })

  it('een antwoord dat nog loopt krijgt geen blokken', () => {
    const el = render(data, { settled: false })
    expect(blokken(el)).toHaveLength(0)
  })

  it('een ingehouden antwoord krijgt geen blokken', () => {
    const ingehouden = { role: 'assistant', done: true, content: 'Dit antwoord is ingehouden.', bronnen: [], controle: ['x'] }
    const el = render(ingehouden)
    expect(blokken(el)).toHaveLength(0)
    expect(el.textContent).not.toContain('n.v.t.')
  })
})
