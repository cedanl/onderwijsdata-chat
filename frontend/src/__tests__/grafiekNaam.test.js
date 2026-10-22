// @vitest-environment jsdom
// #588 (mobiel B3): de grafiek zelf krijgt role="img" met de beschrijving als naam. Niet de wrapper met de
// CSV-knop: role="img" maakt alles erin presentatie, en de knop moet een knop blijven.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return createElement('div', { className: 'plot-stub' }) } }))

import { Message } from '../pages/ChatPage'
import { figuurBeschrijving } from '../figuurBeschrijving'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container

async function render(figuur) {
  const msg = { id: 1, role: 'assistant', content: '', done: true, figures: [{ label: 'Instroom', json: JSON.stringify(figuur) }] }
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(Message, { msg, onSend: vi.fn(), busy: false })) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const STAAF = {
  data: [{ type: 'bar', x: ['2023', '2024'], y: [518940, 475460] }],
  layout: { title: { text: 'Mbo-studenten' }, xaxis: { title: { text: 'Jaar' } }, yaxis: { title: { text: 'Aantal' } } },
}
const focusbaar = el => [...el.querySelectorAll('button, a[href], input, select, textarea, [tabindex]')]
  .map(e => e.className)

describe('PlotlyFigure: toegankelijke naam (#588)', () => {
  it('zet role="img" en de beschrijving op het element rond de grafiek, niet op de wrapper', async () => {
    await render(STAAF)
    const wrap = container.querySelector('.plotly-figure-wrap')
    const grafiek = container.querySelector('[role="img"]')

    expect(grafiek).not.toBeNull()
    expect(grafiek.getAttribute('aria-label')).toBe(figuurBeschrijving(STAAF))
    expect(grafiek.querySelector('.plot-stub')).not.toBeNull()
    expect(wrap.getAttribute('role')).toBeNull()
    expect(wrap.hasAttribute('aria-label')).toBe(false)
  })

  it('houdt de CSV-knop en de waardentabel (#664) buiten elke role="img"', async () => {
    await render(STAAF)
    const csv = container.querySelector('.csv-download-btn')

    expect(csv).not.toBeNull()
    expect(csv.closest('[role="img"]')).toBeNull()
    expect(container.querySelector('.waarden-details').closest('[role="img"]')).toBeNull()
    expect(focusbaar(container.querySelector('.plotly-figure-wrap'))).toEqual(['csv-download-btn', 'tabel-scroll'])
  })

  it('geeft een figuur zonder beschrijving geen role', async () => {
    await render({ data: [], layout: {} })
    expect(container.querySelector('.plotly-figure-wrap')).not.toBeNull()
    expect(container.querySelector('[role="img"]')).toBeNull()
    expect(container.querySelector('[aria-label]')).toBeNull()
  })
})
