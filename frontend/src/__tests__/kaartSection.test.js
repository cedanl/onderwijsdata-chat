// @vitest-environment jsdom
// #906: de kaart van het regiodashboard. Plotly haalt de basiskaart anders van cdn.plot.ly, wat de CSP tegenhoudt
// (gemeten: de kaart bleef leeg). Hier: de basiskaart staat klaar vóór Plotly tekent, de kaart sleept niet (#740), een
// fout van Plotly geeft de melding en de tabel, en wie niet op de kaart past wordt genoemd. react-plotly is nagebootst.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

const plot = vi.hoisted(() => ({ props: null, assets: null }))

vi.mock('react-plotly.js', () => ({
  default: function PlotStub(props) {
    plot.props = props
    plot.assets = window.PlotlyGeoAssets?.topojson?.europe_50m ?? null
    return createElement('div', { className: 'plot-stub' })
  },
}))

import { KaartSection } from '../components/dashboards/shared/charts-kaart'
import { KAART_HOOGTE } from '../components/dashboards/shared/kaart-figuur'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const figuur = (zonder = []) => JSON.stringify({
  data: [
    { type: 'scattergeo', mode: 'markers', name: 'Concurrenten', lon: [4.9], lat: [52.37], text: ['Hogeschool van Amsterdam'] },
    { type: 'scattergeo', mode: 'markers+text', name: 'Hogeschool Utrecht', lon: [5.11], lat: [52.09], text: ['Hogeschool Utrecht'], textfont: { size: 12, color: '#1E40AF' } },
  ],
  layout: {
    height: 340,
    geo: { scope: 'europe', resolution: 50, landcolor: '#F8FAFC' },
    meta: {
      data: [
        { Instelling: 'Hogeschool Utrecht', Plaats: 'Utrecht', Rol: 'eigen instelling' },
        { Instelling: 'Hogeschool van Amsterdam', Plaats: 'Amsterdam', Rol: 'concurrent' },
      ],
      zonder_locatie: zonder,
    },
  },
})

let root
let container

async function render(json) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(KaartSection, { figureJson: json })) })
  // De basiskaart en Plotly laden apart (dynamic import, lazy); wacht tot de stub getekend is.
  for (let i = 0; i < 100 && !container.querySelector('.plot-stub'); i++) {
    await act(async () => { await new Promise(r => setTimeout(r, 20)) })
  }
}

beforeEach(() => {
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  delete window.PlotlyGeoAssets
  plot.props = null
  plot.assets = null
})
afterEach(async () => {
  await act(async () => { root?.unmount() })
  container?.remove()
  delete window.matchMedia
})

describe('KaartSection (#906)', () => {
  it('zet de basiskaart uit de eigen bundel klaar voordat Plotly tekent', async () => {
    await render(figuur())
    expect(container.querySelector('.plot-stub')).not.toBeNull()
    expect(plot.assets?.type).toBe('Topology')
  })

  it('geeft de kaart een vaste hoogte, geen sleepmodus en letters van 13 px', async () => {
    await render(figuur())
    const { layout, style, config } = plot.props
    expect(layout.dragmode).toBe(false)
    expect(layout.height).toBe(KAART_HOOGTE)
    expect(style.height).toBe(KAART_HOOGTE)
    expect(config.scrollZoom).toBe(false)
    expect(layout.legend.font.size).toBeGreaterThanOrEqual(12.5)
    // De kaartkaart knipt niets af: geen maxHeight of overflow:hidden meer.
    const kaart = container.querySelector('.chart-card')
    expect(kaart.style.maxHeight).toBe('')
    expect(kaart.style.overflow).toBe('')
  })

  it('noemt de instellingen in een beschrijving en zet ze in een tabel', async () => {
    await render(figuur())
    const beeld = container.querySelector('[role="img"]')
    expect(beeld.getAttribute('aria-label')).toBe(
      'Kaart met 2 instellingen in de regio, op benaderde plaatscoördinaten: Hogeschool Utrecht (eigen instelling), Hogeschool van Amsterdam.',
    )
    const tabel = container.querySelector('details.waarden-details table')
    expect([...tabel.querySelectorAll('th')].map(th => th.textContent)).toEqual(['Instelling', 'Plaats', 'Rol'])
    expect(tabel.querySelectorAll('tbody tr')).toHaveLength(2)
  })

  it('noemt de instellingen die niet op de kaart staan', async () => {
    await render(figuur(['Hogeschool Ergens']))
    expect(container.querySelector('.kaart-zonder-locatie').textContent)
      .toBe('Niet op de kaart, want de plaats is onbekend: Hogeschool Ergens.')
  })

  it('zegt niets over ontbrekende plaatsen als alles op de kaart staat', async () => {
    await render(figuur())
    expect(container.querySelector('.kaart-zonder-locatie')).toBeNull()
  })

  it('toont de melding en de tabel als Plotly de kaart niet tekent', async () => {
    await render(figuur())
    await act(async () => { plot.props.onError(new Error('unexpected error while fetching topojson file')) })
    expect(container.querySelector('.plot-stub')).toBeNull()
    expect(container.querySelector('[role="alert"]').textContent).toContain('De kaart kon niet worden getekend.')
    expect(container.querySelectorAll('table tbody tr')).toHaveLength(2)
  })

  it('tekent niets zonder figuur', async () => {
    await render(null)
    expect(container.textContent).toBe('')
  })
})
