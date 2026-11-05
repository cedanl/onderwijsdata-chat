// @vitest-environment jsdom
// #907: een klik op een legenda-item zet die reeks aan of uit, ook bij de eerste klik op een reeks die verborgen begint.
// Zes dashboardgrafieken hadden een eigen legendahandler die `meta.hidden = !meta.hidden` deed. Bij een reeks met
// `hidden: true` (de peers in de trend van diploma's per eerstejaars) is `meta.hidden` eerst null, dus de eerste klik zette hem op
// true en de reeks bleef weg. Chart.js doet het standaard goed. De test rendert de drie dashboards met de fixtures,
// vangt elke grafiek die react-chartjs-2 zou tekenen, en klikt in een echte Chart.js elke legenda-regel aan.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { Chart, registerables, BasicPlatform } from 'chart.js'
import dashboards from './fixtures/dashboards.json'

const getekend = vi.hoisted(() => [])
const payloads = vi.hoisted(() => ({}))
vi.mock('react-chartjs-2', () => ({
  Bar: function BarStub({ data, options }) { getekend.push({ type: 'bar', data, options }); return null },
  Line: function LineStub({ data, options }) { getekend.push({ type: 'line', data, options }); return null },
}))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))
vi.mock('../api', async importOriginal => ({
  ...(await importOriginal()),
  fetchDashboardData: vi.fn(async endpoint => payloads[endpoint.replace('/api/dashboard/', '')] ?? {}),
}))

import { InlineDashboardMijnInstelling, InlineDashboardArbeidsmarkt, InlineDashboardNationaal } from '../components/dashboards'

Chart.register(...registerables)
globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

// Een canvas zonder DOM: Chart.js rekent de legenda en de zichtbaarheid uit, tekenen doet niets.
function nepCanvas() {
  const canvas = { width: 600, height: 300, style: {} }
  const opslag = { canvas, measureText: () => ({ width: 10 }) }
  canvas.getContext = () => new Proxy(opslag, {
    get: (doel, sleutel) => (sleutel in doel ? doel[sleutel] : () => {}),
    set: (doel, sleutel, waarde) => { doel[sleutel] = waarde; return true },
  })
  return canvas
}

function echteGrafiek({ type, data, options }) {
  return new Chart(nepCanvas(), {
    type,
    platform: BasicPlatform,
    data: structuredClone({ labels: data.labels, datasets: data.datasets.map(d => ({ ...d })) }),
    options: { ...options, animation: false, responsive: false },
  })
}

let root
let container

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = container = undefined
  getekend.length = 0
})

beforeEach(() => {
  for (const k of Object.keys(payloads)) delete payloads[k]
  Object.assign(payloads, structuredClone(dashboards))
})

async function teken(Dashboard) {
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(Dashboard, { instelling: dashboards.regio.instelling })) })
  await act(async () => { await new Promise(r => setTimeout(r, 0)) })
  return getekend.filter(g => g.options?.plugins?.legend?.display !== false && g.data?.datasets?.length)
}

function klikElkeRegel(grafiek) {
  const chart = echteGrafiek(grafiek)
  try {
    const { legend } = chart
    return legend.legendItems.map(item => {
      const voor = chart.isDatasetVisible(item.datasetIndex)
      chart.options.plugins.legend.onClick.call(legend, {}, item, legend)
      return { label: item.text, voor, na: chart.isDatasetVisible(item.datasetIndex) }
    })
  } finally {
    chart.destroy()
  }
}

describe('legenda van de dashboardgrafieken (#907)', () => {
  it.each([
    ['Mijn instelling', InlineDashboardMijnInstelling],
    ['Arbeidsmarkt', InlineDashboardArbeidsmarkt],
    ['Landelijk', InlineDashboardNationaal],
  ])('%s: één klik zet elke reeks om, ook een die verborgen begint', async (_naam, Dashboard) => {
    const grafieken = await teken(Dashboard)
    expect(grafieken.length).toBeGreaterThan(0)
    for (const grafiek of grafieken) {
      for (const { label, voor, na } of klikElkeRegel(grafiek)) {
        expect({ label, na }).toEqual({ label, na: !voor })
      }
    }
  })

  it('de peers in de trend van diploma\'s per eerstejaars beginnen verborgen en verschijnen bij de eerste klik', async () => {
    // Alleen mbo heeft deze trend (#898); de fixture is een hogeschool, dus hier een mbo-payload met twee cohorten.
    payloads.rendement = {
      instelling: payloads.regio.instelling, gevonden: true, type: 'mbo',
      definitie: { naam: "Diploma's na 3 jaar per eerstejaars", termijn: 3 },
      rendement_per_jaar: { 2021: 0.9, 2022: 0.88 },
      benchmark_rendement: { 2021: 0.8, 2022: 0.85 },
      peers_rendement: { Albeda: { 2021: 0.94, 2022: 0.94 }, Zadkine: { 2022: 0.89 } },
    }
    const grafieken = await teken(InlineDashboardMijnInstelling)
    const trend = grafieken.find(g => g.data.datasets.some(d => d.hidden))
    expect(trend?.data.datasets.filter(d => d.hidden).map(d => d.label)).toEqual(['Albeda', 'Zadkine'])
    const peerKlikken = klikElkeRegel(trend).filter(k => ['Albeda', 'Zadkine'].includes(k.label))
    expect(peerKlikken).toEqual([
      { label: 'Albeda', voor: false, na: true },
      { label: 'Zadkine', voor: false, na: true },
    ])
  })
})
