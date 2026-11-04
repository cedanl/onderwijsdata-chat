// @vitest-environment jsdom
// Dashboardcijfers heten wat ze tellen en tellen op tot hun totaal (#899).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-chartjs-2', () => ({
  Bar: function BarStub({ data }) { return createElement('pre', { 'data-chart': 'bar' }, JSON.stringify(data)) },
  Line: function LineStub({ data }) { return createElement('pre', { 'data-chart': 'line' }, JSON.stringify(data)) },
}))

import { buildLeerwegenData, HoofdgroepenChart, LEERWEGEN_MBO } from '../components/dashboards/shared/charts-sector'

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

describe('mbo-leerwegen (#899)', () => {
  it('tekent Extraneus mee, zodat de leerwegen optellen tot het totaal ingeschrevenen', () => {
    const leerwegen = {
      2024: { BBL: 4000, 'BOL voltijd': 14000, 'BOL deeltijd': 0, Extraneus: 200 },
      2025: { BBL: 4100, 'BOL voltijd': 14100, 'BOL deeltijd': 0, Extraneus: 234 },
    }
    const data = buildLeerwegenData(leerwegen)

    expect(LEERWEGEN_MBO).toContain('Extraneus')
    expect(data.datasets.map(d => d.label)).toEqual(LEERWEGEN_MBO)
    const som2025 = data.datasets.reduce((s, d) => s + d.data[1], 0)
    expect(som2025).toBe(4100 + 14100 + 234)
  })
})

describe('HoofdgroepenChart (#899)', () => {
  it('noemt TOTAAL MBO ingeschrevenen, geen eerstejaars of sectorkamers', () => {
    const el = render(createElement(HoofdgroepenChart, { perHoofdgroep: { 'Zorg en welzijn': 5000, Entree: 300 }, dark: false }))
    const tekst = el.textContent

    expect(tekst).toContain('Ingeschrevenen per hoofdgroep')
    expect(tekst).toContain('Geen eerstejaars')
    expect(tekst).not.toMatch(/sectorkamer/i)
    expect(tekst).not.toMatch(/eerstejaars per hoofdgroep/i)
    const data = JSON.parse(el.querySelector('[data-chart="bar"]').textContent)
    expect(data.datasets[0].label).toBe('Ingeschrevenen')
    expect(data.labels).toEqual(['Zorg en welzijn', 'Entree'])
  })
})
