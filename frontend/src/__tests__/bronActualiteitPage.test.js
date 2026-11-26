// @vitest-environment jsdom
// #1266: de pagina "Actualiteit van de bronnen" (/bronnen) toont wat /api/bronactualiteit geeft, rekent zelf niets uit
// en zegt "onbekend" waar de server niets weet. Een verwachte editie staat er alleen met haar bron. UWV toont de
// leeftijd van de stand in de woorden van ouderdom_tekst (#1219). De regel onder een antwoord: actualiteitRegel.test.js.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import axe from 'axe-core'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))
vi.mock('../api', () => ({
  fetchBronActualiteit: vi.fn(),
  fetchCatalogCounts: () => Promise.resolve({}),
}))

import { fetchBronActualiteit } from '../api'
import BronActualiteitPage, { TITEL } from '../pages/BronActualiteitPage'
import HomePage from '../pages/HomePage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const PLANNING = "Op 14 december 2026 verschijnen de definitieve cijfers over het studiejaar 2025/'26."
const dataset = velden => ({
  id: '85423NED', titel: 'Hoger onderwijs; ingeschrevenen', url: 'https://opendata.cbs.nl/#/CBS/nl/dataset/85423NED/table',
  laatste_periode: "2025/'26", laatste_wijziging: '2026-03-12', status: 'voorlopig', frequentie: 'Jaarlijks',
  verwachte_volgende_editie: 'onbekend', verwachte_volgende_editie_bron: 'onbekend', verwachte_volgende_editie_url: 'onbekend',
  gecontroleerd_op: '2026-10-21', samenvatting: 'frequentie: Jaarlijks, laatste update 2026-03-12', ...velden,
})
const bron = (sleutel, naam, velden = {}) => ({
  bron: sleutel, naam, titel: `${naam} voluit`, url: 'https://example.org', bereikbaar: 'bereikbaar',
  laatste_periode: 'verschilt per dataset', laatste_wijziging: '2026-03-12', status: 'deels voorlopig',
  frequentie: 'Jaarlijks', verwachte_volgende_editie: 'onbekend', verwachte_volgende_editie_bron: 'onbekend',
  datasets: [dataset({ id: `${sleutel}-1` })], ...velden,
})
const OVERZICHT = {
  bronnen: [
    bron('cbs', 'CBS', {
      datasets: [
        dataset({
          verwachte_volgende_editie: PLANNING,
          verwachte_volgende_editie_bron: 'CBS, tabelinformatie 85423NED (Wanneer komen er nieuwe cijfers?)',
          verwachte_volgende_editie_url: 'https://opendata.cbs.nl/#/CBS/nl/dataset/85423NED/table',
        }),
        // Een verwachte editie zonder bron telt niet, en een veld dat de server niet stuurt is "onbekend".
        dataset({ id: '85424NED', verwachte_volgende_editie: '1 januari 2027', verwachte_volgende_editie_bron: 'onbekend', frequentie: null }),
      ],
    }),
    bron('duo', 'DUO', { bereikbaar: 'niet bereikbaar', melding: 'DUO is op dit moment niet bereikbaar. Wat hier staat is de laatst bekende stand uit de catalogus.' }),
    bron('rio', 'RIO', { status: 'onbekend', laatste_wijziging: 'onbekend' }),
    bron('uwv', 'UWV', { laatste_periode: '2023-05-16', ouderdom: { tekst: 'ruim 3 jaar', maanden: 42, verouderd: true } }),
    bron('roa', 'ROA', { bereikbaar: 'onbekend' }),
    bron('skdb', 'SKDB', { status: 'definitief' }),
  ],
  uitleg: 'Uit de catalogus.',
}

let root
let container

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(MemoryRouter, null, element)) })
}

async function renderPagina(antwoord = Promise.resolve(OVERZICHT)) {
  fetchBronActualiteit.mockReturnValue(antwoord)
  await render(createElement(BronActualiteitPage))
  await act(async () => {})
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.clearAllMocks()
})

const sectie = naam => [...container.querySelectorAll('section.bronact-bron')].find(s => s.querySelector('h2').textContent.startsWith(naam))
const kern = (naam, kop) => [...sectie(naam).querySelectorAll('.bronact-kern > div')].find(d => d.querySelector('dt').textContent === kop)?.querySelector('dd').textContent
const rij = (naam, id) => [...sectie(naam).querySelectorAll('tbody tr')].find(r => r.querySelector('th').textContent.includes(id))

describe('de pagina Actualiteit van de bronnen (#1266)', () => {
  it('heeft een paginatitel en een kop, en één sectie per bron in de volgorde van de server', async () => {
    await renderPagina()
    expect(document.title).toBe(`${TITEL} — openEDUdata+`)
    expect(container.querySelector('h1').textContent).toBe(TITEL)
    expect([...container.querySelectorAll('section.bronact-bron h2')].map(h => h.firstChild.textContent.trim()))
      .toEqual(['CBS', 'DUO', 'RIO', 'UWV', 'ROA', 'SKDB'])
  })

  it('toont per bron de kerngegevens, en "onbekend" waar de server niets weet', async () => {
    await renderPagina()
    expect(kern('CBS', 'Laatste wijziging')).toBe('2026-03-12')
    expect(kern('CBS', 'Status')).toBe('deels voorlopig')
    expect(kern('CBS', 'Frequentie')).toBe('Jaarlijks')
    expect(kern('RIO', 'Status')).toBe('onbekend')
    expect(kern('RIO', 'Laatste wijziging')).toBe('onbekend')
    expect(kern('ROA', 'Bereikbaar')).toBe('onbekend')
    expect(rij('CBS', '85424NED').children[4].textContent).toBe('onbekend')
  })

  it('toont een datum zoals de server hem stuurt, niet omgerekend', async () => {
    await renderPagina()
    const tijd = rij('CBS', '85423NED').querySelector('time')
    expect(tijd.getAttribute('dateTime')).toBe('2026-03-12')
    expect(tijd.textContent).toBe('2026-03-12')
  })

  it('toont een verwachte editie alleen met haar bron', async () => {
    await renderPagina()
    const met = rij('CBS', '85423NED').children[5]
    expect(met.textContent).toContain(PLANNING)
    expect(met.textContent).toContain('(bron: CBS, tabelinformatie 85423NED')
    expect(met.querySelector('a').getAttribute('href')).toBe('https://opendata.cbs.nl/#/CBS/nl/dataset/85423NED/table')
    const zonder = rij('CBS', '85424NED').children[5]
    expect(zonder.textContent).toBe('onbekend')
    expect(container.textContent).not.toContain('1 januari 2027')
  })

  it('toont de UWV-ouderdom met de tekst van ouderdom_tekst (#1219)', async () => {
    await renderPagina()
    expect(kern('UWV', 'Leeftijd van de stand')).toBe('ruim 3 jaar oud (verouderd)')
    expect(kern('CBS', 'Leeftijd van de stand')).toBeUndefined()
  })

  it('zegt dat een bron niet bereikbaar is, en toont de rest gewoon', async () => {
    await renderPagina()
    expect(kern('DUO', 'Bereikbaar')).toBe('nee, de bron antwoordt nu niet')
    expect(sectie('DUO').querySelector('.bronact-melding').textContent).toContain('niet bereikbaar')
    expect(kern('CBS', 'Bereikbaar')).toBe('ja, de bron antwoordt')
  })

  it('zegt het als de server niet antwoordt, met een knop om het opnieuw te proberen', async () => {
    await renderPagina(Promise.reject(new Error('API 500')))
    expect(container.querySelector('[role="alert"]').textContent).toContain('kon niet worden opgehaald')
    fetchBronActualiteit.mockReturnValue(Promise.resolve(OVERZICHT))
    await act(async () => { container.querySelector('.bronact-fout button').click() })
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.querySelectorAll('section.bronact-bron')).toHaveLength(6)
  })

  it('heeft geen ernstige axe-bevindingen, ook met de tabellen open', async () => {
    await renderPagina()
    await act(async () => { for (const d of container.querySelectorAll('details')) d.open = true })
    const { violations } = await axe.run(container, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
      rules: { region: { enabled: false }, 'html-has-lang': { enabled: false } },
    })
    expect(violations.filter(v => ['serious', 'critical'].includes(v.impact)).map(v => v.id)).toEqual([])
  })

  it('zet elke tabel in een eigen scrollregio met een naam', async () => {
    await renderPagina()
    for (const tabel of container.querySelectorAll('table')) {
      const regio = tabel.parentElement
      expect(regio.className).toBe('tabel-scroll')
      expect(regio.getAttribute('role')).toBe('region')
      expect(regio.getAttribute('aria-label')).toMatch(/^Datasets van /)
    }
  })
})

// 320 px (WCAG 1.4.10): jsdom rekent geen layout; dit legt de CSS-afspraken vast die de pagina smal houden.
describe('de pagina op 320 px', () => {
  const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
  const regel = kiezer => new RegExp(`(?:^|})\\s*${kiezer.replace(/[.]/g, '\\.')}\\s*{([^}]*)}`).exec(css)?.[1] ?? ''

  it('heeft geen vaste breedte, alleen een maximum, en breekt lange woorden af', () => {
    expect(regel('.bronact-page')).toMatch(/max-width:\s*960px/)
    expect(regel('.bronact-page')).not.toMatch(/(?:^|;)\s*width:/)
    expect(regel('.bronact-page')).toMatch(/overflow-wrap:\s*break-word/)
  })

  it('laat de kerngegevens stapelen tot één kolom', () => {
    expect(regel('.bronact-kern')).toMatch(/minmax\(min\(13rem,\s*100%\),\s*1fr\)/)
  })

  it('laat de brede tabel binnen zijn regio scrollen, niet de pagina', () => {
    expect(regel('.tabel-scroll')).toMatch(/overflow-x:\s*auto/)
    expect(regel('.tabel-scroll')).toMatch(/max-width:\s*100%/)
  })
})

describe('de link naar de pagina', () => {
  it('staat onderaan de startpagina', async () => {
    await render(createElement(HomePage))
    const link = container.querySelector('a[href="/bronnen"]')
    expect(link.textContent).toBe('Actualiteit van de bronnen')
  })
})
