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
    // Met geciteerde getallen is er altijd een export (#544): de knop met de cijfers uit het antwoord.
    const el = render(ALLEEN_CITATIES)
    expect(blokken(el).map(b => [b.dataset.blok, b.dataset.status])).toEqual([
      ['citaties', 'aanwezig'], ['telling', 'n.v.t.'], ['export', 'aanwezig'], ['bronnen', 'n.v.t.'],
    ])
    expect([...blok(el, 'export').querySelectorAll('.data-export-btn')].map(k => k.textContent)).toEqual([
      'Download cijfers als CSV',
    ])
    for (const kind of ['telling', 'bronnen']) {
      expect(blok(el, kind).querySelector('dd').textContent).toBe('n.v.t.')
    }
    const zonder = render({ ...ALLEEN_CITATIES, citaties: [{ getal: '7.912', vastgesteld: false }] })
    expect(blok(zonder, 'export').querySelector('dd').textContent).toBe('n.v.t.')
  })

  // #605: "Hoeveel vrouwelijke mbo-studenten in 2021/22 en 2024/25?" liep via get_cbs_data met een filter op
  // twee schooljaren en verder niets. De server noemt zo'n volledig getoonde selectie nu als tabel (tool_end
  // export_key), dus de knop hangt niet af van citaties in de tekst: ook een tabel zonder geciteerde getallen
  // krijgt hem, en zonder tabel-key én zonder citaties is de export bewust n.v.t.
  const TABEL = 'Vrouwelijke mbo-studenten:\n\n| Schooljaar | Studenten |\n|---|---|\n| 2021/22 | 248.930 |\n| 2024/25 | 230.450 |'
  const lader = exportKey => ({ name: 'get_cbs_data', label: 'CBS data opgehaald', done: true, exportKey, dataKey: 'cbs:85354NED:c7a8bce6' })
  const tabelantwoord = (tools, citaties) => ({ role: 'assistant', done: true, content: TABEL, tools, citaties, bronnen: [CBS] })

  it('geven een tabel uit een volledig getoonde laderselectie de CSV-knop, ook zonder geciteerde getallen', () => {
    const el = render(tabelantwoord([lader('cbs:85354NED:c7a8bce6')], []))
    expect(blok(el, 'export').dataset.status).toBe('aanwezig')
    expect([...el.querySelectorAll('.data-export-btn')].map(k => k.textContent)).toEqual(['Download data als CSV'])
  })

  it('zetten de export op n.v.t. bij een tabel zonder tabel-key en zonder geciteerde getallen', () => {
    const el = render(tabelantwoord([lader(null)], []))
    expect(blok(el, 'export').querySelector('dd').textContent).toBe('n.v.t.')
    expect(el.querySelectorAll('.data-export-btn')).toHaveLength(0)
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

  it('slaan een bron over die geen tekst is, in plaats van te crashen', () => {
    const el = render({ ...VIJF_ANTWOORDEN[1], bronnen: [DUO, { titel: CBS }, null] })
    expect([...blok(el, 'bronnen').querySelectorAll('li')].map(li => li.textContent)).toEqual([DUO])
  })

  it('tonen de Telling en de CSV-knoppen niet ook nog buiten de blokken', () => {
    const el = render(VIJF_ANTWOORDEN[1])
    expect(el.querySelectorAll('details.telling')).toHaveLength(1)
    expect(el.querySelectorAll('.data-export')).toHaveLength(1)
    expect(el.querySelector('.answer-blocks details.telling')).not.toBeNull()
    expect(el.querySelector('.message-bubble').textContent).not.toContain('**Telling**')
  })
})

// #621: elke bronregel linkt naar de bronpagina die de server meestuurt, met dezelfde http(s)-keuring als het rapport.
describe('bronregels als link naar de bronpagina', () => {
  const PER_BRON = {
    CBS: [CBS, 'https://opendata.cbs.nl/ODataApi/OData/85423NED'],
    DUO: [DUO, 'https://onderwijsdata.duo.nl/datasets/p01hoinges'],
    RIO: ['RIO erkenningen, peildatum 2026-10-09', 'https://lod.onderwijsregistratie.nl/api/rio/v2/erkenningen'],
    UWV: ['UWV · UWV Open Match (uwv-open-match-data), peildatum 2023-05-16', 'https://data.overheid.nl/dataset/uwv-open-match-data'],
    ROA: ['ROA · AIS tot 2030 (ais2030), versie v20251218', 'https://doi.org/10.34894/DVQTOG'],
  }
  const regels = el => [...blok(el, 'bronnen').querySelectorAll('li')]

  for (const [naam, [bron, url]] of Object.entries(PER_BRON)) {
    it(`${naam}: de regel is een link die in een nieuw tabblad opent, met de regel als tekst`, () => {
      const el = render({ ...VIJF_ANTWOORDEN[0], bronnen: [bron], bronlinks: { [bron]: url } })
      const [li] = regels(el)
      const a = li.querySelector('a')
      expect(li.children).toHaveLength(1)
      expect(a.getAttribute('href')).toBe(url)
      expect(a.getAttribute('target')).toBe('_blank')
      expect(a.getAttribute('rel')).toBe('noopener noreferrer')
      expect(a.textContent).toBe(bron)
      expect(li.textContent).toBe(bron)
      expect(a.getAttribute('aria-label')).toBe(`${bron} (opent in een nieuw tabblad)`)
    })
  }

  it('een regel zonder link blijft tekst naast een regel met link', () => {
    const el = render({ ...VIJF_ANTWOORDEN[1], bronlinks: { [CBS]: PER_BRON.CBS[1] } })
    const [duo, cbs] = regels(el)
    expect(duo.querySelector('a')).toBeNull()
    expect(duo.textContent).toBe(DUO)
    expect(cbs.querySelector('a').getAttribute('href')).toBe(PER_BRON.CBS[1])
  })

  it.each([
    ['javascript:alert(1)'], ['data:text/html,x'], ['//evil.example'], ['/relatief'], ['ftp://x'], [' https://x'],
    [42], [null], [{ href: 'https://x' }],
  ])('een slecht adres (%j) wordt nooit een link', url => {
    const el = render({ ...VIJF_ANTWOORDEN[0], bronlinks: { [DUO]: url } })
    expect(el.querySelector('.answer-bronnen a')).toBeNull()
    expect(regels(el).map(li => li.textContent)).toEqual([DUO])
  })

  it.each([[[PER_BRON.DUO[1]]], ['https://x'], [null]])('bronlinks die geen object zijn (%j) geven tekst', bronlinks => {
    const el = render({ ...VIJF_ANTWOORDEN[0], bronlinks })
    expect(el.querySelector('.answer-bronnen a')).toBeNull()
    expect(regels(el).map(li => li.textContent)).toEqual([DUO])
  })

  it('een bericht van vóór de links toont de bronnen als tekst, zoals het was', () => {
    const met = render({ ...VIJF_ANTWOORDEN[1], bronlinks: {} })
    const oud = render(VIJF_ANTWOORDEN[1])
    expect(oud.querySelector('.answer-bronnen a')).toBeNull()
    expect(blok(oud, 'bronnen').innerHTML).toBe(blok(met, 'bronnen').innerHTML)
    expect(blok(oud, 'bronnen').querySelector('dd').innerHTML).toBe(`<ul class="answer-bronnen"><li>${DUO}</li><li>${CBS}</li></ul>`)
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
