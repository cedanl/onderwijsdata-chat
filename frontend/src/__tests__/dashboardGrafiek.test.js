// @vitest-environment jsdom
// #905 en #906: een grafiek van een dashboard heeft een tekstalternatief en een waardentabel, zoals een figuur in de
// chat (#588, #664); de knop Abs/% zegt wat hij doet en of hij aan staat; de opties van Chart.js geven ruime tikdoelen,
// letters van 13 px en geen animatie bij prefers-reduced-motion.
// jsdom heeft geen canvas, en een Chart.js zonder context loopt vast bij een update; daarom is react-chartjs-2
// nagebootst zoals het zich gedraagt: een canvas met role="img" en de overige props erop.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-chartjs-2', async () => {
  const { createElement: maak } = await import('react')
  // eslint-disable-next-line no-unused-vars -- data en options gaan naar Chart.js, niet naar het canvas
  const Canvas = ({ data, options, ...canvas }) => maak('canvas', { role: 'img', ...canvas })
  return { Line: Canvas, Bar: Canvas }
})
import { alsFiguur, waardeAsTitel } from '../components/dashboards/shared/grafiek-figuur'
import { figuurBeschrijving } from '../figuurBeschrijving'
import { figuurTabel } from '../figuurTabel'
import { ChartCard, Grafiek, horizontalBarOpts, buildIndexChartOpts, SectorTrendChart } from '../components/dashboards/shared/index'
import { pasStandaardenToe, FONT_GROOTTE, labelRegels } from '../components/dashboards/shared/chart-opts'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const LIJN = {
  labels: ['2021', '2022', '2023'],
  datasets: [
    { label: 'Hogeschool Utrecht', data: [0, 4, 9] },
    { label: 'Regio', data: [0, 2, null] },
    { label: 'Lege concurrent', data: [null, null, null] },
  ],
}

describe('alsFiguur (#905)', () => {
  it('beschrijft een lijngrafiek met titel, assen en per reeks de eerste en laatste waarde', () => {
    const figuur = alsFiguur('line', LIJN, { titel: 'Ingeschrevenen per jaar', waardeAs: '% verandering t.o.v. eerste jaar' })
    expect(figuurBeschrijving(figuur)).toBe(
      'Lijngrafiek: Ingeschrevenen per jaar. X-as: Jaar, y-as: % verandering t.o.v. eerste jaar. ' +
      'Hogeschool Utrecht: 3 punten, eerste 2021: 0, laatste 2023: 9. Regio: 2 punten, eerste 2021: 0, laatste 2022: 2.',
    )
  })

  it('geeft een tabel met een rij per label en een kolom per reeks, zonder lege reeks', () => {
    expect(figuurTabel(alsFiguur('line', LIJN))).toEqual({
      kolommen: ['Jaar', 'Hogeschool Utrecht', 'Regio'],
      rijen: [['2021', 0, 0], ['2022', 4, 2], ['2023', 9, null]],
      labels: 1,
    })
  })

  it('noemt de labelkolom van een staafdiagram zoals de grafiek opgeeft', () => {
    const data = { labels: ['HU', 'HvA'], datasets: [{ label: 'Ingeschrevenen', data: [38000, 41000] }] }
    expect(figuurTabel(alsFiguur('bar', data, { categorie: 'Instelling' })).kolommen).toEqual(['Instelling', 'Ingeschrevenen'])
    expect(figuurBeschrijving(alsFiguur('bar', data, { titel: 'Marktpositie' }))).toMatch(/^Staafdiagram: Marktpositie\./)
  })

  it('leest de titel van de waardeas uit de opties, ook van een liggende grafiek', () => {
    expect(waardeAsTitel(buildIndexChartOpts(false))).toBe('% verandering t.o.v. het startjaar')
    expect(waardeAsTitel(horizontalBarOpts(false))).toBeUndefined()
  })
})

describe('chart-opts (#905, #906)', () => {
  const nepStandaarden = () => ({ font: { size: 12 }, interaction: { mode: 'nearest', intersect: true }, animation: { duration: 1000 } })
  const media = matches => {
    const luisteraars = []
    return { matches, addEventListener: (_, f) => luisteraars.push(f), zet(m) { this.matches = m; luisteraars.forEach(f => f()) } }
  }

  it('zet letters en interactie als standaard: een tik hoeft niet op het punt zelf', () => {
    const d = nepStandaarden()
    pasStandaardenToe(d, media(false))
    expect(d.font.size).toBe(FONT_GROOTTE)
    expect(FONT_GROOTTE).toBeGreaterThanOrEqual(12.5)
    expect(d.interaction).toMatchObject({ mode: 'nearest', intersect: false, axis: 'xy' })
    expect(d.locale).toBe('nl-NL')
    expect(d.animation).toEqual({ duration: 1000 })
  })

  it('zet de animatie uit bij prefers-reduced-motion en volgt een wijziging', () => {
    const d = nepStandaarden()
    const m = media(true)
    pasStandaardenToe(d, m)
    expect(d.animation).toBe(false)
    m.zet(false)
    expect(d.animation).toEqual({ duration: 1000 })
  })

  it('laat een tik op een liggende staaf de hele rij vangen', () => {
    expect(horizontalBarOpts(false).interaction).toEqual({ mode: 'index', axis: 'y', intersect: false })
  })

  // Op 390 px viel de voorkant van een lang label weg: Chart.js geeft de as hoogstens de halve grafiek.
  it('breekt een lang label op de as van een liggende staaf af in regels', () => {
    expect(labelRegels('Techniek')).toBe('Techniek')
    expect(labelRegels('Gedrag & Maatschappij')).toEqual(['Gedrag &', 'Maatschappij'])
    expect(labelRegels('Hogeschool voor de Kunsten Utrecht')).toEqual(['Hogeschool voor de', 'Kunsten Utrecht'])
    const { callback } = horizontalBarOpts(false).scales.y.ticks
    expect(callback.call({ getLabelForValue: () => 'Protestantse Theologische Universiteit' }, 0))
      .toEqual(['Protestantse', 'Theologische', 'Universiteit'])
  })
})

let root
let container

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

afterEach(async () => {
  await act(async () => { root?.unmount() })
  container?.remove()
  vi.restoreAllMocks()
})

describe('Grafiek in een ChartCard (#905)', () => {
  it('geeft het canvas een naam met de cijfers en zet de waarden ingeklapt eronder', async () => {
    await render(createElement(ChartCard, { title: 'Ingeschrevenen per jaar' },
      createElement(Grafiek, { soort: 'line', data: LIJN, options: buildIndexChartOpts(false), hoogte: 200 })))
    const canvas = container.querySelector('canvas')
    expect(canvas.getAttribute('role')).toBe('img')
    expect(canvas.getAttribute('aria-label')).toMatch(/^Lijngrafiek: Ingeschrevenen per jaar\. .*Hogeschool Utrecht: 3 punten/)
    const details = container.querySelector('details.waarden-details')
    expect(details.open).toBe(false)
    expect(details.querySelectorAll('tbody tr')).toHaveLength(3)
    // De titel is een kop onder de sectiekop (h2), niet een div met een aria-label zonder rol.
    expect(container.querySelector('h3.chart-title').textContent).toBe('Ingeschrevenen per jaar')
    expect(container.querySelector('.chart-card').hasAttribute('aria-label')).toBe(false)
  })

  it('heeft een knop Abs/% met een vaste naam en aria-pressed', async () => {
    const data = { labels: ['2022', '2023'], datasets: [{ label: 'Economie', data: [10, 30] }, { label: 'Techniek', data: [30, 10] }] }
    await render(createElement(SectorTrendChart, { data, dark: false }))
    const knop = container.querySelector('button.db-schakel')
    expect(knop.textContent).toBe('Toon als %')
    expect(knop.getAttribute('aria-pressed')).toBe('false')
    await act(async () => { knop.click() })
    expect(knop.textContent).toBe('Toon als %')
    expect(knop.getAttribute('aria-pressed')).toBe('true')
    expect(container.querySelector('tbody tr').textContent).toContain('25')
  })
})
