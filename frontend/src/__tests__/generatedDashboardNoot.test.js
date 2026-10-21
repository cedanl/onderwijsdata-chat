// @vitest-environment jsdom
// #651: in een gegenereerd dashboard staat de afrondingsnoot als tekstregel onder de grafiek, niet als ondertitel in
// de figuur; ook bij een dashboard dat vóór die wijziging is bewaard.
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

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const NOOT = 'De aantallen zijn door CBS afgerond op 10-tallen: een som, verschil of percentage daarvan is niet exact.'
const data = [{ type: 'bar', x: ['2023'], y: [5] }]
const nieuw = { data, layout: { title: { text: 'Instroom' }, meta: { afrondingsnoot: NOOT } } }
const oud = { data, layout: { title: { text: 'Uitval', subtitle: { text: 'De aantallen zijn door CBS afgerond op 10-tallen: een<br>som, verschil of percentage daarvan is niet exact.' } } } }
const zonder = { data, layout: { title: { text: 'Gediplomeerden' } } }

let root
let container

async function render(figures) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(GeneratedDashboard, { spec: { figures_json: figures } })) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  layouts.length = 0
})

describe('afrondingsnoot in een gegenereerd dashboard (#651)', () => {
  it('zet de noot als tekstregel onder de grafiek in de kaart, voor een nieuwe en een bewaarde figuur', async () => {
    await render([JSON.stringify(nieuw), oud, JSON.stringify(zonder)])
    const kaarten = [...container.querySelectorAll('.chart-card')]
    expect(kaarten).toHaveLength(3)
    for (const kaart of kaarten.slice(0, 2)) {
      expect([...kaart.children].map(e => e.className)).toEqual(['plot-stub', 'figuur-noot'])
      expect(kaart.querySelector('p.figuur-noot').textContent).toBe(NOOT)
    }
    expect([...kaarten[2].children].map(e => e.className)).toEqual(['plot-stub'])
    expect(layouts.filter(Boolean).every(l => !l.title?.subtitle)).toBe(true)
  })

  it('zet tekens uit de noot als tekst neer', async () => {
    await render([{ data, layout: { meta: { afrondingsnoot: '<img src=x onerror=alert(1)>' } } }])
    expect(container.querySelector('.figuur-noot').textContent).toBe('<img src=x onerror=alert(1)>')
    expect(container.querySelector('img')).toBeNull()
  })
})
