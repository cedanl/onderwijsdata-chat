// @vitest-environment jsdom
// #651: de afrondingsnoot stond als ondertitel van 11 px in de grafiek, niet te selecteren en op een telefoon te klein.
// In de chat staat hij nu als tekstregel onder de grafiek, buiten het element met role="img".
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const layouts = vi.hoisted(() => [])
vi.mock('react-plotly.js', () => ({
  default: function PlotStub({ layout }) {
    layouts.push(layout)
    return createElement('div', { className: 'plot-stub' })
  },
}))

import { Message } from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const NOOT = 'De aantallen zijn door CBS afgerond op 10-tallen: een som, verschil of percentage daarvan is niet exact. Gebruik waar het kan een gepubliceerd totaal.'
const data = [{ type: 'bar', x: ['2023', '2024'], y: [518940, 475460] }]
const assen = { xaxis: { title: { text: 'Jaar' } }, yaxis: { title: { text: 'Aantal' } } }
const titel = { text: 'Ingeschrevenen HO', font: { size: 16, color: '#222' } }
const NIEUW = { data, layout: { title: titel, ...assen, margin: { t: 60 }, meta: { afrondingsnoot: NOOT } } }
const OUD = {
  data,
  layout: {
    title: {
      ...titel, yref: 'container', yanchor: 'top', y: 0.98,
      subtitle: { text: 'De aantallen zijn door CBS afgerond op 10-tallen: een som,<br>verschil of percentage daarvan is niet exact. Gebruik<br>waar het kan een gepubliceerd totaal.', font: { size: 11, color: '#666' } },
    },
    ...assen,
    margin: { t: 100 },
  },
}
const ZONDER = { data, layout: { title: titel, ...assen, margin: { t: 60 } } }

let root
let container

async function render(figuur) {
  const msg = { id: 1, role: 'assistant', content: '', done: true, figures: [{ label: 'Ingeschrevenen', json: JSON.stringify(figuur) }] }
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(Message, { msg, onSend: vi.fn(), busy: false })) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  layouts.length = 0
})

const noten = () => [...container.querySelectorAll('p.figuur-noot')]

describe('afrondingsnoot onder een grafiek in de chat (#651)', () => {
  for (const [naam, figuur] of [['een nieuwe figuur (layout.meta)', NIEUW], ['een bewaarde figuur met ondertitel', OUD]]) {
    it(`zet de noot van ${naam} als één tekstregel na de grafiek, buiten role="img"`, async () => {
      await render(figuur)
      const [noot, ...meer] = noten()
      expect(meer).toEqual([])
      expect(noot.textContent).toBe(NOOT)
      const wrap = container.querySelector('.plotly-figure-wrap')
      expect(noot.parentElement).toBe(wrap)
      expect(noot.closest('[role="img"]')).toBeNull()
      const grafiek = wrap.querySelector('[role="img"]')
      expect(grafiek).not.toBeNull()
      expect(grafiek.compareDocumentPosition(noot) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })

    it(`geeft Plotly ${naam} zonder ondertitel en zonder notemarge`, async () => {
      await render(figuur)
      const layout = layouts.at(-1)
      expect(layout.title).not.toHaveProperty('subtitle')
      expect(layout.margin.t).toBe(32)
    })
  }

  it('toont geen noot bij een figuur zonder afronding', async () => {
    await render(ZONDER)
    expect(container.querySelector('.plotly-figure-wrap')).not.toBeNull()
    expect(noten()).toEqual([])
  })

  it('zet tekens uit de noot als tekst neer, niet als HTML', async () => {
    await render({ ...NIEUW, layout: { ...NIEUW.layout, meta: { afrondingsnoot: '<img src=x onerror=alert(1)>' } } })
    expect(noten()[0].textContent).toBe('<img src=x onerror=alert(1)>')
    expect(container.querySelector('img')).toBeNull()
  })
})

describe('opmaak van de noot (#651)', () => {
  const css = readFileSync(join(import.meta.dirname, '..', 'styles.css'), 'utf8')
  const regel = css.match(/\.figuur-noot\s*{([^}]*)}/)?.[1] ?? ''

  it('volgt --font-label (12,5 px op een telefoon) en de gedempte tekstkleur van het thema', () => {
    expect(regel).toMatch(/font-size:\s*var\(--font-label\)/)
    expect(regel).toMatch(/color:\s*var\(--gray-500\)/)
  })
})
