// @vitest-environment jsdom
// #1181: de teksten en begrippen op de drie vaste dashboards (Mijn instelling, Landelijk, Arbeidsmarkt). Eén render van
// elk dashboard met de payloads van de server; de tests lezen wat een gebruiker leest: tekst, aria-labels, tooltips en
// de namen van de reeksen en assen van de grafieken.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import dashboards from './fixtures/dashboards.json'

// De grafiekstub toont wat Chart.js zou tekenen als tekst: de naam van het canvas, de reeksen en de astitels.
function astitels(opties) {
  return Object.values(opties?.scales ?? {}).map(as => as?.title?.text).filter(Boolean)
}
function GrafiekStub({ data, options, ...rest }) {
  const teksten = [...(data?.datasets ?? []).map(d => d.label), ...astitels(options)].filter(Boolean)
  return createElement('div', { role: 'img', 'aria-label': rest['aria-label'] }, teksten.join(' | '))
}
vi.mock('react-chartjs-2', () => ({ Bar: props => GrafiekStub(props), Line: props => GrafiekStub(props) }))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

const payloads = {}
vi.mock('../api', async importOriginal => ({
  ...(await importOriginal()),
  fetchDashboardData: vi.fn(async endpoint => payloads[endpoint] ?? {}),
}))

import { InlineDashboardMijnInstelling } from '../components/dashboards/mijn-instelling/index'
import { InlineDashboardNationaal } from '../components/dashboards/nationaal/index'
import { InlineDashboardArbeidsmarkt } from '../components/dashboards/arbeidsmarkt-consolidated/index'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

const HBO = dashboards.regio
// Een hogeschool zonder genoeg collega's in de regio vergelijkt met heel Nederland (#926); een wo-instelling ook.
const LANDELIJK = {
  ...HBO,
  benchmark: {
    ...HBO.benchmark,
    label: 'Landelijk, 18 andere hogescholen — te weinig hogescholen van vergelijkbare omvang in provincie Utrecht',
    populatie: 'hogescholen in heel Nederland',
    regio_type: 'nationaal',
    regio_naam: 'Nederland',
  },
}

// De bronbestanden van de app, zonder tests en fixtures.
function bestanden(map) {
  return readdirSync(map, { withFileTypes: true }).flatMap(e => {
    const pad = `${map}${e.name}`
    if (e.isDirectory()) return e.name.startsWith('__') ? [] : bestanden(`${pad}/`)
    return /\.(js|jsx)$/.test(e.name) ? [pad] : []
  })
}
// Commentaarregels en commentaar achter code vallen weg; een URL (`://`) blijft staan.
const zonderCommentaar = tekst => tekst.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/.*$/gm, '')

let root
let container

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = container = undefined
  for (const k of Object.keys(payloads)) delete payloads[k]
})

async function renderIn(element) {
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
  await act(async () => { await new Promise(r => setTimeout(r, 0)) })
}

async function mijnInstelling(regio, rendement = dashboards.rendement) {
  payloads['/api/dashboard/regio'] = regio
  payloads['/api/dashboard/rendement'] = rendement
  await renderIn(createElement(InlineDashboardMijnInstelling, { instelling: regio.instelling }))
}

async function nationaal(payload = dashboards.nationaal) {
  payloads['/api/dashboard/nationaal'] = payload
  await renderIn(createElement(InlineDashboardNationaal, { instelling: payload.instelling }))
}

const MATCH_DUIDING = { drempel: 1.2, vacatures_peildatum: '2023-05-16', diplomajaren: [2023, 2024, 2025], sectormapping: {} }

async function arbeidsmarkt(regio = HBO) {
  payloads['/api/dashboard/arbeidsmarktmatch'] = { ...dashboards.arbeidsmarktmatch, match_duiding: MATCH_DUIDING }
  payloads['/api/dashboard/regio'] = regio
  await renderIn(createElement(InlineDashboardArbeidsmarkt, { instelling: dashboards.arbeidsmarktmatch.instelling }))
}

// Alles wat een gebruiker of schermlezer van de pagina krijgt, per stuk: de tekst van elk blad van de pagina en de
// aria-labels, titels en alt-teksten.
function teksten() {
  const stukken = []
  for (const el of container.querySelectorAll('*')) {
    if (!el.children.length && el.textContent.trim()) stukken.push(el.textContent.trim())
    for (const a of ['aria-label', 'title', 'alt']) if (el.getAttribute(a)) stukken.push(el.getAttribute(a))
  }
  return stukken
}
const alles = () => teksten().join('\n')
const kaartMetTitel = titel => [...container.querySelectorAll('.chart-card')].find(k => k.querySelector('.chart-title')?.textContent === titel)
const sectieKop = titel => [...container.querySelectorAll('h2')].find(h => h.textContent === titel)

// #1130: bij een landelijke vergelijkingsgroep zegt geen tekst "regio", "benchmark-regio" of "regiototaal".
describe('de gebiedsteksten volgen de vergelijkingsgroep (#1130)', () => {
  const REGIOWOORDEN = /benchmark-regio|regiototaal|in de regio|Regio totaal/i

  it('landelijk: geen titel, ondertitel, legenda, tabelbijschrift of alt-tekst zegt "regio"', async () => {
    await mijnInstelling(LANDELIJK)
    const tekst = alles()
    expect(tekst).not.toMatch(REGIOWOORDEN)
    // De regio van de instelling zelf (badge) blijft: dat is haar adres, niet de vergelijkingsgroep.
    expect(tekst).toContain('Regio Midden-Utrecht')
  })

  it('landelijk: de kaart, de tabel en de grafieken noemen heel Nederland', async () => {
    await mijnInstelling(LANDELIJK)
    expect(sectieKop('Locaties in heel Nederland')).toBeTruthy()
    expect(sectieKop('Locaties in heel Nederland').parentElement.textContent).toContain('Instellingen in heel Nederland (ster = eigen instelling)')
    expect(sectieKop('Overzicht concurrenten').parentElement.textContent).toMatch(/\d+ instellingen in heel Nederland/)
    expect(container.querySelector('caption.sr-only').textContent).toBe('Overzicht concurrenten in heel Nederland, gesorteerd op ingeschrevenen')
    expect(kaartMetTitel('Marktaandeel over tijd').textContent).toContain('% van het landelijke totaal ingeschrevenen')
    expect(kaartMetTitel('Marktpositie 2025/26').textContent).toContain('per instelling in heel Nederland')
  })

  it('regionaal: de regiotekst blijft staan', async () => {
    await mijnInstelling(HBO)
    expect(sectieKop('Locaties in de regio')).toBeTruthy()
    expect(sectieKop('Locaties in de regio').parentElement.textContent).toContain('Instellingen in de regio (ster = eigen instelling)')
    expect(sectieKop('Overzicht concurrenten').parentElement.textContent).toMatch(/\d+ instellingen in de regio/)
    expect(kaartMetTitel('Marktaandeel over tijd').textContent).toContain('% van het regiototaal ingeschrevenen')
    expect(kaartMetTitel('Marktpositie 2025/26').textContent).toContain('per instelling in de regio')
    expect(alles()).not.toMatch(/benchmark-regio/)
  })

  it.each([
    ['landelijk', LANDELIJK, 'hogescholen in heel Nederland'],
    ['regionaal', HBO, 'hogescholen in arbeidsmarktregio Midden-Utrecht'],
  ])('%s: de diplomeringskop en de grafiek eronder noemen dezelfde vergelijkingsgroep', async (_soort, regio, groep) => {
    await mijnInstelling(regio)
    expect(sectieKop('Diplomering').parentElement.textContent).toContain(`vergeleken met ${groep}`)
    expect(kaartMetTitel('Gediplomeerden per jaar').textContent).toContain(groep)
  })
})

// #1136: dezelfde DUO-telling van personen heet overal "Ingeschrevenen"; "Inschrijvingen" is een telling van inschrijvingen.
describe('één woord voor de telling van personen (#1136)', () => {
  const sectorTitels = () => [...container.querySelectorAll('.chart-title, h2')].map(k => k.textContent).filter(t => /per sector over tijd/.test(t))

  it('Mijn instelling en Landelijk noemen de sectortrend "Ingeschrevenen per sector over tijd"', async () => {
    await mijnInstelling(HBO)
    expect(sectorTitels()).toEqual(['Ingeschrevenen per sector over tijd'])
    act(() => root.unmount())
    container.remove()
    await nationaal()
    expect(container.querySelector('h2:not(:empty)') && [...container.querySelectorAll('.db-sectie-sub')].map(e => e.textContent)).toContain('Ingeschrevenen per sector over tijd')
  })

  it.each([
    ['Mijn instelling', () => mijnInstelling(HBO)],
    ['Landelijk', () => nationaal()],
    ['Arbeidsmarkt', () => arbeidsmarkt()],
  ])('%s: geen tekst over "inschrijvingen" bij een telling van personen', async (_naam, laad) => {
    await laad()
    expect(alles()).not.toMatch(/inschrijvingen/i)
  })
})

// #1137: één spelling per begrip.
describe('één spelling per begrip (#1137)', () => {
  it('de arbeidsmarkt schrijft "beroepencluster" en Mijn instelling "Regiototaal"', async () => {
    await arbeidsmarkt()
    expect(alles()).not.toMatch(/beroepscluster/i)
    act(() => root.unmount())
    container.remove()
    await mijnInstelling(HBO)
    const labels = [...container.querySelectorAll('.kpi-label')].map(e => e.textContent)
    expect(labels).toContain('Regiototaal 2025/26')
    expect(alles()).not.toMatch(/regio totaal/i)
  })

  // De afgekeurde varianten staan nergens in de broncode van de app (tests en commentaar niet meegeteld).
  it('geen afgekeurde variant in frontend/src', () => {
    const afgekeurd = /beroepscluster|Regio totaal|regio-totaal/i
    const root = `${join(__dirname, '..')}/`
    const overtreders = bestanden(root)
      .filter(pad => afgekeurd.test(zonderCommentaar(readFileSync(pad, 'utf8'))))
      .map(pad => pad.slice(root.length))
    expect(overtreders).toEqual([])
  })
})
