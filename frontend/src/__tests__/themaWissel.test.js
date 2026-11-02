// @vitest-environment jsdom
// #834: één useDarkMode voor de hele app, en een gegenereerd dashboard dat een themawissel volgt zonder een render
// van buitenaf.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

const layouts = vi.hoisted(() => [])
vi.mock('react-plotly.js', () => ({
  default: function PlotStub({ layout }) {
    layouts.push(layout)
    return createElement('div', { className: 'plot-stub' })
  },
}))

import GeneratedDashboard from '../components/GeneratedDashboard'
import { useDarkMode as appHook } from '../hooks/useDarkMode'
import { useDarkMode as dashboardHook } from '../components/dashboards/shared'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  document.documentElement.classList.remove('dark')
  layouts.length = 0
})

describe('themawissel (#834)', () => {
  it('de dashboards gebruiken dezelfde useDarkMode als de rest van de app', () => {
    expect(dashboardHook).toBe(appHook)
  })

  it('een grafiek in een gegenereerd dashboard krijgt na een themawissel de donkere tekstkleur', async () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    const figuur = { data: [{ type: 'bar', x: ['2023'], y: [5] }], layout: {} }
    await act(async () => { root.render(createElement(GeneratedDashboard, { spec: { figures_json: [figuur] } })) })
    expect(layouts.at(-1).font.color).toBe('#374151')

    await act(async () => { document.documentElement.classList.add('dark') })
    expect(layouts.at(-1).font.color).toBe('#E2E8F0')
  })
})
