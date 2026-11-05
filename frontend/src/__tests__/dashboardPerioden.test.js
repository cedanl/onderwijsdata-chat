// @vitest-environment jsdom
// #904 deel 2: een jaar op de dashboards zegt wat het is (schooljaar 2025/26 of diplomajaar 2024, het soort uit de
// payload), elk getal staat in Nederlandse notatie via fmt, en een vergelijking tussen instellingen leent geen ander
// jaar voor een peer zonder cijfers in het laatste jaar.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-chartjs-2', () => ({
  Bar: function BarStub({ data }) { return createElement('pre', { 'data-chart': 'bar' }, JSON.stringify(data)) },
  Line: function LineStub({ data }) { return createElement('pre', { 'data-chart': 'line' }, JSON.stringify(data)) },
}))

import { jaarLabel, asJaar } from '../schooljaar'
import { fmt } from '../components/dashboards/shared/getal'
import { buildIndexChartOpts, horizontalBarOpts } from '../components/dashboards/shared/chart-opts'
import { buildBenchmarkLineData, buildPeerLinesData } from '../components/dashboards/shared/chart-builders'
import { buildMarktaandeelData, MarktaandeelChart, buildGroeiRankingData, GroeiRankingChart } from '../components/dashboards/shared/charts-markt'
import { PeersTable } from '../components/dashboards/shared/charts-peers'
import { OndergrensNoot } from '../components/dashboards/shared/ondergrens'
import { DemografieKpis } from '../components/dashboards/shared/kpis'

const PERIODEN = { ingeschrevenen: 'schooljaar', eerstejaars: 'schooljaar', cohorten: 'schooljaar', gediplomeerden: 'diplomajaar' }

let container
let root
function render(el) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root.render(el))
  return container
}
afterEach(() => {
  if (root) act(() => root.unmount())
  container?.remove()
  root = container = undefined
})

describe('jaarLabel en asJaar', () => {
  it('schrijft een schooljaar als 2025/26 en een diplomajaar met zijn naam', () => {
    expect(jaarLabel(2025, 'schooljaar')).toBe('2025/26')
    expect(jaarLabel('2024', 'diplomajaar')).toBe('diplomajaar 2024')
    expect(asJaar(2025, 'schooljaar')).toBe('2025/26')
    expect(asJaar(2024, 'diplomajaar')).toBe('2024')
  })

  it('beweert niets zonder soort of jaar', () => {
    expect(jaarLabel(2025)).toBe('2025')
    expect(asJaar(2025)).toBe('2025')
    expect(jaarLabel(null, 'schooljaar')).toBe('')
  })
})

describe('Nederlandse notatie (#904)', () => {
  it('fmt: komma als decimaalteken, punt als duizendtal', () => {
    expect(fmt(52.3)).toBe('52,3')
    expect(fmt(12345)).toBe('12.345')
    expect(fmt(null)).toBe('—')
  })

  it('de as en de tooltip van een indexgrafiek gebruiken fmt', () => {
    const opts = buildIndexChartOpts(false)
    expect(opts.scales.y.ticks.callback(12.5)).toBe('12,5%')
    expect(opts.plugins.tooltip.callbacks.label({ parsed: { y: 1250 }, dataset: { label: 'Eigen' } })).toBe('Eigen: +1.250%')
  })

  it('de tooltip van een liggende staaf gebruikt fmt', () => {
    expect(horizontalBarOpts(false, '%').plugins.tooltip.callbacks.label({ raw: 1234.5 })).toBe(' 1.234,5%')
  })

  it('het aandeel vrouw staat met een komma', () => {
    const el = render(createElement(DemografieKpis, { pctVrouw: 52.3, vrouw: 523, man: 477, laatsteJaar: 2025, perioden: PERIODEN }))
    expect(el.textContent).toContain('52,3% vrouw')
    expect(el.textContent).toContain('Geslachtsverhouding 2025/26')
  })
})

describe('schooljaren op de assen en in de koppen (#904)', () => {
  it('de lijnen van ingeschrevenen tonen schooljaren; de berekening blijft bij de jaartallen', () => {
    const data = buildBenchmarkLineData({ 2024: 100, 2025: 110 }, { 2024: 50, 2025: 55 }, 'Eigen', 'Regio', '#000', '#999', 'schooljaar')
    expect(data.labels).toEqual(['2024/25', '2025/26'])
    expect(data.startjaar).toBe(2024)
    expect(data.datasets[0].data).toEqual([0, 10])
  })

  it('de lijnen van gediplomeerden houden het diplomajaar als jaartal', () => {
    const data = buildPeerLinesData({ 2023: 10, 2024: 12 }, {}, 'Eigen', '#000', '#999', 'diplomajaar')
    expect(data.labels).toEqual(['2023', '2024'])
  })

  it('de ondergrensnoot noemt de jaren naar hun soort', () => {
    const el = render(createElement(OndergrensNoot, { reeksen: [
      { label: 'Ingeschrevenen', onderdrukt: { 2024: 1 }, soort: 'schooljaar' },
      { label: 'Gediplomeerden', onderdrukt: { 2022: 1, 2023: 2 }, soort: 'diplomajaar' },
    ] }))
    expect(el.textContent).toContain('Ingeschrevenen in 2024/25; Gediplomeerden in diplomajaar 2022, 2023: ten minste')
  })

  it('de groeiranking noemt start- en eindjaar als schooljaar', () => {
    const DATA = {
      laatste_jaar: 2025,
      perioden: PERIODEN,
      ingeschrevenen: { 2022: 100, 2025: 110 },
      benchmark: { peers: { ingeschrevenen: { 'Peer A': { 2022: 50, 2025: 60 } } } },
    }
    const el = render(createElement(GroeiRankingChart, { data: buildGroeiRankingData(DATA, 'Eigen', false), dark: false }))
    expect(el.textContent).toContain('Groei ingeschrevenen 2022/23–2025/26')
  })
})

describe('één jaar voor iedereen in de marktpositie en de concurrententabel (#927-regel)', () => {
  // Peer B heeft geen cijfers over 2025; zijn laatste jaar is 2024.
  const DATA = {
    laatste_jaar: 2025,
    perioden: PERIODEN,
    ingeschrevenen: { 2024: 480, 2025: 500 },
    benchmark: {
      peers: {
        ingeschrevenen: {
          'Hogeschool A': { 2024: 790, 2025: 800 },
          'Hogeschool B': { 2023: 150, 2024: 9999 },
        },
      },
    },
  }

  it('buildMarktaandeelData leent geen ander jaar: een peer zonder 2025 valt weg en staat in weggelaten', () => {
    const uit = buildMarktaandeelData(DATA, 'Eigen', false)
    expect(uit.labels).toEqual(['Hogeschool A', 'Eigen'])
    expect(uit.datasets[0].data).toEqual([800, 500])
    expect(uit.weggelaten).toEqual(['Hogeschool B'])
    expect(uit.jaar).toBe(2025)
  })

  it('de grafiek noemt het schooljaar en wie er zonder cijfers over dat jaar is', () => {
    const el = render(createElement(MarktaandeelChart, { data: buildMarktaandeelData(DATA, 'Eigen', false), dark: false }))
    expect(el.textContent).toContain('Marktpositie 2025/26')
    expect(el.textContent).toContain('Niet getoond (geen cijfers over 2025/26): Hogeschool B.')
    expect(el.textContent).not.toContain('9999')
  })

  it('de concurrententabel toont zo\'n peer zonder getal, niet met dat van een ander jaar', () => {
    const el = render(createElement(PeersTable, { data: DATA, instelling: 'Eigen' }))
    expect(el.textContent).toContain('Ingeschrevenen 2025/26')
    const rijen = [...el.querySelectorAll('tbody tr')].map(tr => [...tr.querySelectorAll('td')].map(td => td.textContent))
    expect(rijen.at(-1)).toEqual(['—', 'Hogeschool B', 'geen gegevens', '—'])
    expect(el.textContent).not.toContain('9.999')
  })
})
