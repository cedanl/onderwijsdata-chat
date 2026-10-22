// @vitest-environment jsdom
// #664: onder een grafiek in de chat staat een ingeklapte tabel met al haar waarden, voor wie geen tooltip kan
// gebruiken (touch, schermlezer). react-plotly is nagebootst; de tabel komt niet uit Plotly maar uit de figuur.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: () => createElement('div', { className: 'plot-stub' }) }))

import { Message } from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const STAAF = {
  data: [{ type: 'bar', x: [2023, 2024], y: [518940, 475460.5] }],
  layout: { title: { text: 'Mbo-studenten' }, meta: { x: 'Jaar', y: 'Studenten', data: [{ Jaar: 2023, Studenten: 518940 }, { Jaar: 2024, Studenten: 475460.5 }] } },
}

let root
let container

async function render(figuur) {
  const msg = { id: 1, role: 'assistant', content: '', done: true, figures: [{ label: 'Grafiek aangemaakt', json: JSON.stringify(figuur) }] }
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(Message, { msg, onSend: vi.fn(), busy: false })) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const details = () => container.querySelector('.waarden-details')
const koppen = () => [...details().querySelectorAll('th')].map(th => th.textContent)
const cellen = () => [...details().querySelectorAll('tbody tr')].map(tr => [...tr.cells].map(td => td.textContent))

describe('waardentabel onder een grafiek (#664)', () => {
  it('staat ingeklapt onder de grafiek, met "Toon de waarden" als knop', async () => {
    await render(STAAF)
    expect(details().open).toBe(false)
    expect(details().querySelector('summary').textContent).toBe('Toon de waarden')
    expect(container.querySelector('.plot-stub').compareDocumentPosition(details()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('toont elke waarde in Nederlandse notatie en laat het jaar staan', async () => {
    await render(STAAF)
    expect(koppen()).toEqual(['Jaar', 'Studenten'])
    expect(cellen()).toEqual([['2023', '518.940'], ['2024', '475.460,5']])
  })

  it('zet meerdere reeksen naast elkaar, een lege cel waar een reeks geen punt heeft', async () => {
    await render({
      data: [],
      layout: { meta: { x: 'Jaar', y: 'Studenten', data: [
        { reeks: 'hbo', Jaar: 2023, Studenten: 1200 }, { reeks: 'hbo', Jaar: 2024, Studenten: 1300 },
        { reeks: 'wo', Jaar: 2024, Studenten: 800 },
      ] } },
    })
    expect(koppen()).toEqual(['Jaar', 'hbo', 'wo'])
    expect(cellen()).toEqual([['2023', '1.200', ''], ['2024', '1.300', '800']])
  })

  it('ontbreekt bij een grafiek die niet te exporteren is: dan staat de melding er', async () => {
    await render({ data: [{ type: 'bar', x: ['a', 'b'], y: [1] }], layout: {} })
    expect(container.querySelector('[role="alert"]').textContent).toContain('niet te exporteren')
    expect(details()).toBeNull()
  })
})
