// @vitest-environment jsdom
// #632: een kaart die niet getekend is, toont een melding en de tabel; een getekende kaart en een gewone grafiek
// niet. react-plotly is nagebootst: de stub roept onInitialized of onError aan zoals de echte doet.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

const plot = vi.hoisted(() => ({ gedrag: null }))

vi.mock('react-plotly.js', async () => {
  const { useEffect } = await import('react')
  return {
    default: function PlotStub(props) {
      // eslint-disable-next-line react-hooks/exhaustive-deps -- once, like the real component on mount
      useEffect(() => { plot.gedrag?.(props) }, [])
      return createElement('div', { className: 'plot-stub' })
    },
  }
})

import { Message } from '../pages/ChatPage'
import { NUL_BEVESTIGING } from '../kaartStatus'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const KAART = {
  data: [{ type: 'choroplethmap', locations: ['PV20', 'PV27'], z: [24310, 117600] }],
  layout: {
    title: { text: 'Mbo-studenten per provincie' },
    meta: {
      type: 'choropleth', location_col: 'Provincie', value_col: 'Studenten',
      data: [{ Provincie: 'Groningen', Studenten: 24310, _kaartcode: 'PV20' }, { Provincie: 'Noord-Holland', Studenten: 117600 }],
    },
  },
}
const STAAF = { data: [{ type: 'bar', x: ['2023', '2024'], y: [518940, 475460] }], layout: { title: { text: 'Mbo' } } }

// Een maplibre-kaart die meteen klaar is met de gegeven getekende gebieden en kort daarna 'idle' wordt.
const kaartMet = vormen => ({
  _fullLayout: {
    map: {
      _subplot: {
        map: {
          on(naam, f) { if (naam === 'idle') Promise.resolve().then(f) }, off() {}, loaded: () => true,
          queryRenderedFeatures: () => vormen,
        },
      },
    },
  },
})

let root
let container

async function render(figuur, gedrag) {
  plot.gedrag = gedrag
  const msg = { id: 1, role: 'assistant', content: '', done: true, figures: [{ label: 'Kaart aangemaakt', json: JSON.stringify(figuur) }] }
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(Message, { msg, onSend: vi.fn(), busy: false })) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const wrap = () => container.querySelector('.plotly-figure-wrap')
const tabellen = () => [...wrap().querySelectorAll('table')]
const alleenWaardentabel = () => tabellen().length === 1 && tabellen()[0].closest('.waarden-details') !== null
const cellen = () => [...wrap().querySelectorAll('tbody tr')].map(tr => [...tr.cells].map(td => td.textContent))

describe('kaart die niet getekend is (#632)', () => {
  it('toont bij een fout van Plotly de melding en de tabel met plaats en waarde', async () => {
    await render(KAART, props => props.onError(new Error('Map error.')))
    const melding = wrap().querySelector('[role="alert"]')
    expect(melding.textContent).toContain('De kaart kon niet worden getekend')
    expect(melding.textContent).toContain('tabel')
    expect([...wrap().querySelectorAll('th')].map(th => th.textContent)).toEqual(['Provincie', 'Studenten'])
    expect(cellen()).toEqual([['Groningen', '24.310'], ['Noord-Holland', '117.600']])
    expect(wrap().querySelector('caption').textContent).toBe('Mbo-studenten per provincie')
  })

  it('noemt de kaart dan niet "Kaart aangemaakt" en verbergt de lege kaart', async () => {
    await render(KAART, props => props.onError(new Error('Map error.')))
    expect(wrap().textContent).not.toContain('Kaart aangemaakt')
    expect(wrap().textContent).toContain('Kaart niet getekend')
    expect(wrap().querySelector('.plot-stub').closest('[hidden]')).not.toBeNull()
  })

  it('toont dan alleen de terugvaltabel, geen tweede waardentabel (#664)', async () => {
    await render(KAART, props => props.onError(new Error('Map error.')))
    expect(tabellen()).toHaveLength(1)
    expect(wrap().querySelector('.waarden-details')).toBeNull()
  })

  it('houdt de CSV-knop als er geen kaart is', async () => {
    await render(KAART, props => props.onError(new Error('Map error.')))
    expect(wrap().querySelector('.csv-download-btn')).not.toBeNull()
  })

  it('toont de melding als de kaart nul gebieden tekent, na de bevestiging', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    await render(KAART, props => props.onInitialized({}, kaartMet([])))
    await act(async () => {})
    expect(wrap().querySelector('[role="alert"]')).toBeNull()
    await act(async () => { vi.advanceTimersByTime(NUL_BEVESTIGING) })
    expect(wrap().querySelector('[role="alert"]').textContent).toContain('De kaart kon niet worden getekend')
    expect(cellen()).toHaveLength(2)
    vi.useRealTimers()
  })

  // #642: na een niet-fatale fout bleven melding en tabel staan, ook als de kaart daarna toch tekende.
  it('haalt melding en tabel weg als de kaart na een fout alsnog tekent', async () => {
    const luisteraars = {}
    const vormen = []
    const gd = { _fullLayout: { map: { _subplot: { map: {
      on(naam, f) { luisteraars[naam] = f }, off(naam) { delete luisteraars[naam] }, loaded: () => false,
      queryRenderedFeatures: () => vormen,
    } } } } }
    await render(KAART, props => props.onInitialized({}, gd))
    await act(async () => { luisteraars.error() })
    expect(wrap().querySelector('[role="alert"]')).not.toBeNull()
    vormen.push({ id: 0, properties: { ct: [5, 52] }, layer: { type: 'fill' } })
    await act(async () => { luisteraars.idle() })
    expect(wrap().querySelector('[role="alert"]')).toBeNull()
    expect(wrap().querySelector('[role="img"], [hidden]')?.hidden ?? false).toBe(false)
  })

  it('slaat rijen over die geen object zijn', async () => {
    const kapot = { ...KAART, layout: { ...KAART.layout, meta: { ...KAART.layout.meta, data: [null, ['Utrecht', 1], 'tekst', { Provincie: 'Zeeland', Studenten: 9000 }] } } }
    await render(kapot, props => props.onError(new Error('Map error.')))
    expect(cellen()).toEqual([['Zeeland', '9.000']])
  })

  it('verwijst naar het antwoord als de figuur geen rijen meegeeft', async () => {
    const zonderRijen = { ...KAART, layout: { title: KAART.layout.title } }
    await render(zonderRijen, props => props.onError(new Error('Map error.')))
    expect(wrap().querySelector('[role="alert"]').textContent).toContain('Controleer de cijfers in het antwoord')
    expect(wrap().querySelector('table')).toBeNull()
  })
})

describe('kaart die getekend is en gewone grafieken (#632)', () => {
  // Sinds #664 staat onder elke grafiek een ingeklapte waardentabel; de terugvaltabel komt er niet bij.
  it('toont bij een getekende kaart geen melding en alleen de ingeklapte waardentabel', async () => {
    await render(KAART, props => props.onInitialized({}, kaartMet([{ id: 'PV20', layer: { type: 'fill' } }])))
    expect(wrap().querySelector('[role="alert"]')).toBeNull()
    expect(alleenWaardentabel()).toBe(true)
    expect(wrap().textContent).toContain('Kaart aangemaakt')
    expect(wrap().querySelector('[role="img"]').hidden).toBe(false)
  })

  it('negeert een latere fout van een kaart die al getekend is', async () => {
    await render(KAART, props => {
      props.onInitialized({}, kaartMet([{ id: 'PV20', layer: { type: 'fill' } }]))
      props.onError(new Error('later'))
    })
    expect(wrap().querySelector('[role="alert"]')).toBeNull()
  })

  it('laat een gewone grafiek met een fout ongemoeid', async () => {
    await render(STAAF, props => props.onError(new Error('iets')))
    expect(wrap().querySelector('[role="alert"]')).toBeNull()
    expect(alleenWaardentabel()).toBe(true)
  })

  it('meldt niets zolang Plotly geen maplibre-kaart heeft (jsdom)', async () => {
    await render(KAART, props => props.onInitialized({}, { _fullLayout: {} }))
    expect(wrap().querySelector('[role="alert"]')).toBeNull()
  })
})
