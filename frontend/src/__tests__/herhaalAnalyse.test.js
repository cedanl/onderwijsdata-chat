// @vitest-environment jsdom
// "Herhaal deze analyse" (#1240): de knop bij een antwoord met een CBS-tabel, achter "Geavanceerd" (#1269); niet bij
// een rapport, niet bij een antwoord zonder CBS-tabel. De uitkomst staat als tak onder het antwoord, met de zin van de
// server en de stand van toen en nu, en geen tekst zegt dat het eerdere antwoord niet klopte (besluit #1236).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { webcrypto } from 'node:crypto'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import HerhaalAnalyse, { HerhaalUitkomst } from '../components/HerhaalAnalyse'
import { Message } from '../pages/ChatPage'
import { buildReportHtml } from '../reportHtml'
import {
  HERHAAL_KNOP, HERHAAL_NOOT, REDEN_ZONDER_HASH, VASTE_TEKSTEN, antwoordHash, nlDag, standTekst, toontHerhaal,
} from '../herhaalAnalyse'
import { metGeavanceerd } from './helpers/geavanceerd'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const BRON = 'CBS · Ingeschrevenen hbo en wo (85423NED)'
const ANTWOORD = {
  id: 'a1',
  role: 'assistant',
  done: true,
  content: 'Er stonden 367.960 studenten ingeschreven in 2025.',
  bronnen: [BRON],
  citaties: [{ getal: '367.960', vastgesteld: true, stap: 1, tool: 'get_cbs_data', bron: BRON, data_key: 'cbs:85423NED' }],
  tools: [
    { name: 'search_catalog', label: 'Catalogus doorzocht', done: true },
    { name: 'get_cbs_data', label: 'CBS-data geladen', done: true, dataKey: 'cbs:85423NED', exportKey: 'cbs:85423NED' },
  ],
}
const DUO_ANTWOORD = {
  ...ANTWOORD,
  tools: [{ name: 'get_duo_data', label: 'DUO-data geladen', done: true, dataKey: 'duo:p01hoinges:0' }],
}
const ANALYSE_ANTWOORD = {
  ...ANTWOORD,
  tools: [{ name: 'run_analysis', label: 'Eigen berekening', done: true, dataKey: 'cbs:85423NED:analyse:1' }],
}
const BIJGEWERKT = {
  bron: 'cbs',
  tabellen: [{
    dataset: '85423NED',
    titel: 'Ingeschrevenen hbo en wo',
    status: 'bijgewerkt',
    samenvatting: 'Bron bijgewerkt op 15-06-2026; cijfer verschilt: 367.960 → 369.120 (A025294, 2025SJ00; Ingeschrevenen); '
      + 'versie van 14-04-2026 → 15-06-2026.',
    toen: { bijgewerkt_op: '2026-04-14', hash: 'aaaaaaaaaaaa' },
    nu: { bijgewerkt_op: '2026-06-15', hash: 'bbbbbbbbbbbb' },
    verschil: { cellen: 1, eerste: { rij: 'A025294, 2025SJ00', kolom: 'Ingeschrevenen', toen: 367960, nu: 369120 }, rijen_erbij: 0, rijen_weg: 0 },
  }],
  overgeslagen: ['Alleen tabellen van CBS worden nu opnieuw opgehaald; DUO en RIO volgen later.'],
}

let mounted = []

function render(element, aan = true) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  mounted.push({ root, container })
  act(() => root.render(metGeavanceerd(element, aan)))
  return container
}

afterEach(() => {
  for (const { root, container } of mounted) {
    act(() => root.unmount())
    container.remove()
  }
  mounted = []
})

const knop = el => [...el.querySelectorAll('button')].find(b => b.textContent === HERHAAL_KNOP) ?? null
const tekst = el => el.textContent.replace(/\s+/g, ' ').trim()

describe('wanneer de knop er staat (#1240, criterium 1)', () => {
  it('bij een afgerond data-antwoord met een CBS-tabel', () => {
    expect(toontHerhaal(ANTWOORD)).toBe(true)
    expect(toontHerhaal({ ...ANTWOORD, tools: [{ name: 'query_data', done: true, dataKey: 'cbs:85423NED:ab12' }] })).toBe(true)
  })

  it('niet zonder CBS-tabel: alleen DUO of RIO, een eigen berekening of een mislukte stap', () => {
    expect(toontHerhaal(DUO_ANTWOORD)).toBe(false)
    expect(toontHerhaal(ANALYSE_ANTWOORD)).toBe(false)
    expect(toontHerhaal({ ...ANTWOORD, tools: [{ ...ANTWOORD.tools[1], status: 'leeg' }] })).toBe(false)
  })

  it('niet bij een tekst uit code, een fout, een gestopt of nog lopend antwoord', () => {
    for (const msg of [
      { ...ANTWOORD, vast: true }, { ...ANTWOORD, isError: true }, { ...ANTWOORD, stopped: true },
      { ...ANTWOORD, done: false }, { ...ANTWOORD, bronnen: undefined }, { ...ANTWOORD, role: 'user' },
    ]) expect(toontHerhaal(msg)).toBe(false)
  })

  it('onder het antwoord alleen met "Geavanceerd" aan', () => {
    const props = { msg: ANTWOORD, gesprekId: 'c1', settled: true, onSend: () => {}, busy: false }
    expect(knop(render(createElement(Message, props), true))).not.toBeNull()
    expect(knop(render(createElement(Message, props), false))).toBeNull()
  })

  it('niet onder een antwoord zonder CBS-tabel, en niet zonder gesprek', () => {
    expect(knop(render(createElement(Message, { msg: DUO_ANTWOORD, gesprekId: 'c1', settled: true, onSend: () => {} })))).toBeNull()
    expect(knop(render(createElement(Message, { msg: ANTWOORD, settled: true, onSend: () => {} })))).toBeNull()
  })

  it('niet in een rapport', () => {
    const html = buildReportHtml({ title: 'Studenten', onderzoeksvraag: 'Hoeveel?', conclusie: 'Er waren er 367.960.', visualisaties: [] })
    expect(html).not.toContain(HERHAAL_KNOP)
  })

  it('uitgeschakeld met een reden als de browser de sleutel van het antwoord niet kan maken', () => {
    const el = render(createElement(HerhaalAnalyse, { msg: ANTWOORD, gesprekId: 'c1', hashbaar: false }))
    const k = knop(el)
    expect(k.disabled).toBe(true)
    expect(document.getElementById(k.getAttribute('aria-describedby')).textContent).toBe(REDEN_ZONDER_HASH)
  })
})

describe('de herhaling (#1240)', () => {
  it('vraagt de server met het gesprek en de tekst van het antwoord en toont de stand van toen en nu', async () => {
    const herhaal = vi.fn().mockResolvedValue(BIJGEWERKT)
    const el = render(createElement(HerhaalAnalyse, { msg: ANTWOORD, gesprekId: 'c1', herhaal, hashbaar: true }))
    await act(async () => knop(el).click())

    expect(herhaal).toHaveBeenCalledWith('c1', ANTWOORD.content)
    const uitkomst = tekst(el.querySelector('.herhaal-uitkomst'))
    expect(tekst(el.querySelector('.herhaal-tabel-kop'))).toBe('Bron bijgewerkt Ingeschrevenen hbo en wo (85423NED)')
    const zin = tekst(el.querySelector('.herhaal-tabel .herhaal-zin'))
    expect(zin).toContain('Bron bijgewerkt op 15-06-2026; cijfer verschilt: 367.960 → 369.120')
    expect(zin).toContain('versie van 14-04-2026 → 15-06-2026')
    const stand = [...el.querySelectorAll('.herhaal-stand > div')].map(d => `${d.querySelector('dt').textContent}: ${d.querySelector('dd').textContent}`)
    expect(stand).toEqual(['Toen: bijgewerkt op 14-04-2026, inhoudshash aaaaaaaaaaaa', 'Nu: bijgewerkt op 15-06-2026, inhoudshash bbbbbbbbbbbb'])
    expect(tekst(el.querySelector('.herhaal-overgeslagen'))).toContain('DUO en RIO volgen later')
    expect(tekst(el.querySelector('.herhaal-noot'))).toBe(HERHAAL_NOOT)
    // Een tak naast het antwoord: de tekst van het antwoord zelf staat er niet in en is niet vervangen.
    expect(uitkomst).not.toContain(ANTWOORD.content)
  })

  it('toont "ongewijzigd" en een melding van de bron zoals de server ze geeft', () => {
    const el = render(createElement(HerhaalUitkomst, { uitkomst: { tabellen: [
      { dataset: '85423NED', titel: 'T', status: 'ongewijzigd', samenvatting: 'Ongewijzigd: dezelfde cijfers en dezelfde bronversie (bijgewerkt op 14-04-2026).', toen: { bijgewerkt_op: '2026-04-14', hash: 'a' }, nu: { bijgewerkt_op: '2026-04-14', hash: 'a' } },
      { dataset: '85424NED', titel: 'U', status: 'mislukt', melding: "CBS gaf de data van 'U' niet opnieuw: HTTP 503." },
    ] } }))
    const [ongewijzigd, mislukt] = [...el.querySelectorAll('.herhaal-tabel')]
    expect(ongewijzigd.dataset.status).toBe('ongewijzigd')
    expect(tekst(ongewijzigd.querySelector('.herhaal-tabel-kop'))).toBe('Ongewijzigd T (85423NED)')
    expect(tekst(ongewijzigd.querySelector('.herhaal-zin'))).toMatch(/^Ongewijzigd: dezelfde cijfers en dezelfde bronversie/)
    expect(tekst(mislukt.querySelector('.herhaal-tabel-kop'))).toBe('Niet opgehaald U (85424NED)')
    expect(tekst(mislukt.querySelector('.herhaal-zin'))).toBe("CBS gaf de data van 'U' niet opnieuw: HTTP 503.")
    expect(mislukt.querySelector('.herhaal-stand')).toBeNull()
  })

  it('zegt wat de server meldt als herhalen niet kan (budget, limiet, onbekend antwoord)', async () => {
    const herhaal = vi.fn().mockRejectedValue(new Error('Te veel verzoeken in korte tijd. Probeer het over 30 seconden opnieuw.'))
    const el = render(createElement(HerhaalAnalyse, { msg: ANTWOORD, gesprekId: 'c1', herhaal, hashbaar: true }))
    await act(async () => knop(el).click())

    expect(el.querySelector('[role="alert"]').textContent).toBe('Te veel verzoeken in korte tijd. Probeer het over 30 seconden opnieuw.')
    expect(el.querySelector('.herhaal-uitkomst')).toBeNull()
  })
})

describe('de teksten (#1240, criterium 7)', () => {
  const VERBODEN = ['fout', 'onjuist', 'foutief', 'verkeerd', 'klopt niet', 'incorrect']

  it('zeggen nooit dat het eerdere antwoord niet klopte', async () => {
    const herhaal = vi.fn().mockResolvedValue(BIJGEWERKT)
    const el = render(createElement(HerhaalAnalyse, { msg: ANTWOORD, gesprekId: 'c1', herhaal, hashbaar: true }))
    await act(async () => knop(el).click())
    const zichtbaar = tekst(el).toLowerCase()
    for (const woord of VERBODEN) {
      expect(zichtbaar, woord).not.toContain(woord)
      for (const t of VASTE_TEKSTEN) expect(t.toLowerCase(), `${woord} in ${t}`).not.toContain(woord)
    }
  })
})

describe('de sleutel en de opmaak', () => {
  it('is de sha256 van de tekst, zoals de server (agent/beurtbewijs.py)', async () => {
    const eigen = globalThis.crypto
    Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true })
    try {
      expect(await antwoordHash('abc')).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
    } finally {
      Object.defineProperty(globalThis, 'crypto', { value: eigen, configurable: true })
    }
  })

  it('schrijft de dag als dd-mm-jjjj en een stand met versie en hash', () => {
    expect(nlDag('2026-06-15')).toBe('15-06-2026')
    expect(nlDag(null)).toBe('onbekend')
    expect(standTekst({ bijgewerkt_op: '2026-06-15', hash: 'abc' })).toBe('bijgewerkt op 15-06-2026, inhoudshash abc')
    expect(standTekst(null)).toBeNull()
  })
})
