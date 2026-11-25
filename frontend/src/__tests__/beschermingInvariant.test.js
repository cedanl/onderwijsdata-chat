// @vitest-environment jsdom
// #1269, criterium 6: "Geavanceerd" voegt alleen iets toe en verbergt nooit een beschermende functie. Hetzelfde
// antwoord op bevroren data (een vast bericht, zoals het van de server komt) staat hier twee keer in beeld, met de
// instelling uit en aan; elke beschermende uitvoer moet er in beide staan, met dezelfde tekst.
//
// BESCHERMEND is de lijst van docs/kwaliteit-en-veiligheid.md ("Altijd aan"). Een nieuwe beschermende functie komt
// hier bij, met een plek in ANTWOORD of RAPPORT en een functie die haar uit de pagina leest, en ook in BESCHERMEND van
// tests/test_geavanceerd.py (de kant van de server).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import { Message } from '../pages/ChatPage'
import { buildReportHtml } from '../reportHtml'
import { metGeavanceerd } from './helpers/geavanceerd'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const BRON = 'CBS · Mbo-studenten landelijk (85354NED)'
const ANTWOORD = {
  id: 'a1',
  role: 'assistant',
  done: true,
  content: [
    '**Uitgangspunt:** mbo, landelijk, alle opleidingen.',
    '**Niet meegeteld:** de deelnemers aan een vavo-opleiding.',
    'In 2024 waren er 512.100 mbo-studenten; in de kleinste groepen ≥ 1.250, een ondergrens.',
    'Let op: voorlopige cijfers van CBS.',
    '**Bron en definitie:** CBS StatLine 85354NED, ingeschreven op 1 oktober.',
  ].join('\n\n'),
  controle: ['Het getal 518.940 staat niet in de opgehaalde data.'],
  vervangen: [{ tekst: 'In 2024 waren er 518.940 mbo-studenten.', reden: ['Het getal 518.940 staat niet in de opgehaalde data.'] }],
  citaties: [{
    getal: '512.100', vastgesteld: true, stap: 2, tool: 'get_maat', label: 'Vaste maat',
    bron: BRON, maat: 'Mbo-studenten', selectie: 'Perioden: 2024/25', data_key: 'cbs:85354NED:nep',
  }],
  tools: [
    { name: 'search_catalog', label: 'Catalogus doorzocht', done: true },
    { name: 'get_maat', label: 'Vaste maat', done: true, exportKey: 'cbs:85354NED:nep', snippet: 'import pandas as pd' },
  ],
  bronnen: [BRON],
}
const SCOPEKAART = {
  id: 'a2',
  role: 'assistant',
  done: true,
  content: 'Bedoel je de stad Utrecht of een instelling?',
  clarification: [{ label: 'Hogeschool Utrecht' }, { label: 'Universiteit Utrecht' }, { label: 'De gemeente Utrecht' }],
}
const RAPPORT = {
  title: 'Mbo-studenten',
  onderzoeksvraag: 'Hoeveel mbo-studenten waren er in 2025?',
  conclusie: 'Er waren er 512.100.',
  afwijkingen: ['Je vroeg naar 2025; de laatste cijfers zijn van 2024.'],
  visualisaties: [],
}

const tekst = el => el?.textContent.replace(/\s+/g, ' ').trim() ?? null

// Per beschermende functie: waar ze staat en wat de gebruiker ervan leest. null betekent: ontbreekt.
const BESCHERMEND = {
  'antwoordcontrole': el => tekst(el.querySelector('.message-controle')),
  'intrekking': el => tekst(el.querySelector('.message-ingetrokken')),
  'uitgangspunt': el => [...el.querySelectorAll('p')].map(tekst).find(t => t.startsWith('Uitgangspunt:')) ?? null,
  'niet meegeteld': el => [...el.querySelectorAll('p')].map(tekst).find(t => t.startsWith('Niet meegeteld:')) ?? null,
  'bron en definitie': el => [...el.querySelectorAll('p')].map(tekst).find(t => t.startsWith('Bron en definitie:')) ?? null,
  'ondergrens': el => [...el.querySelectorAll('p')].map(tekst).find(t => t.includes('≥ 1.250')) ?? null,
  'let op': el => [...el.querySelectorAll('p')].map(tekst).find(t => t.startsWith('Let op:')) ?? null,
  'citatie in woorden': el => {
    const knop = el.querySelector('.citatie-getal')
    if (!knop) return null
    act(() => knop.click())
    const uitleg = el.querySelector('[role="note"]')
    // De herkomst in woorden, zonder het uitklapblok met de key: dat hoort bij Geavanceerd.
    const woorden = uitleg && [...uitleg.children].filter(c => c.tagName !== 'DETAILS').map(tekst).join(' | ')
    act(() => knop.click())
    return woorden || null
  },
  'bronnenlijst': el => tekst(el.querySelector('[data-blok="bronnen"] dd')),
  'scopekaart': el => [...el.querySelectorAll('.clarification-btns button')].map(tekst).join(' | ') || null,
  'afwijking van je vraag': (_el, rapport) => /<div class="afwijking" role="note">.*?<\/div>/s.exec(rapport)?.[0] ?? null,
}

let mounted = []

function toon(aan) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  mounted.push({ root, container })
  act(() => root.render(metGeavanceerd(createElement('div', null,
    createElement(Message, { msg: ANTWOORD, onSend: vi.fn(), busy: false, settled: true }),
    createElement(Message, { msg: SCOPEKAART, onSend: vi.fn(), onClarification: vi.fn(), busy: false, settled: true }),
  ), aan)))
  // Het rapport is HTML uit code, buiten React; het staat hier om de lijst compleet te houden.
  const rapport = buildReportHtml(RAPPORT)
  return Object.fromEntries(Object.entries(BESCHERMEND).map(([naam, lees]) => [naam, lees(container, rapport)]))
}

afterEach(() => {
  for (const { root, container } of mounted) {
    act(() => root.unmount())
    container.remove()
  }
  mounted = []
  delete window.matchMedia
})

describe('beschermende functies staan er met en zonder Geavanceerd (#1269)', () => {
  it('zijn er allemaal, met dezelfde tekst, in beide standen', () => {
    window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
    const uit = toon(false)
    const aan = toon(true)

    const ontbreekt = stand => Object.entries(stand).filter(([, waarde]) => !waarde).map(([naam]) => naam)
    expect(ontbreekt(uit)).toEqual([])
    expect(ontbreekt(aan)).toEqual([])
    expect(uit).toEqual(aan)
  })

  it('leest de inhoud die het antwoord draagt', () => {
    window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
    const uit = toon(false)
    expect(uit['antwoordcontrole']).toBe('Let op: Het getal 518.940 staat niet in de opgehaalde data.')
    expect(uit['citatie in woorden']).toContain(BRON)
    expect(uit['citatie in woorden']).toContain('Perioden: 2024/25')
    expect(uit['scopekaart']).toContain('Hogeschool Utrecht')
    expect(uit['afwijking van je vraag']).toContain('Afwijking van je vraag')
  })

  it('maar wat bij Geavanceerd hoort, verschilt wel: de lijst toetst dus echt twee standen', () => {
    window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
    toon(false)
    toon(true)
    const [uit, aan] = mounted.map(m => m.container)
    expect(uit.querySelector('.data-export-btn')).toBeNull()
    expect(aan.querySelector('.data-export-btn')).not.toBeNull()
  })
})
