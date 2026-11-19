// @vitest-environment jsdom
// #1057: een bron die niet live is, zag de gebruiker pas als een tool midden in een vraag faalde. Nu meldt de app het
// bij het openen, en alleen dan: staan alle bronnen live, dan blijft de plek leeg. De melding verdwijnt zelf zodra de
// bron weer antwoordt, zonder dat de pagina herlaadt.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import BronStatusMelding from '../components/BronStatusMelding'
import { VERVERS_MS } from '../hooks/useBronStatus'

const DUO = {
  bron: 'duo',
  naam: 'DUO',
  tekst: 'DUO is op dit moment niet bereikbaar. Antwoorden die DUO-data nodig hebben kunnen falen of ontbreken.',
  laatst_live: null,
}

let container
let root

function antwoord(niet_live, ok = true) {
  return Promise.resolve({ ok, json: () => Promise.resolve({ niet_live }) })
}

async function toon() {
  await act(async () => {
    root.render(createElement(BronStatusMelding))
  })
}

async function ververs() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(VERVERS_MS)
  })
}

beforeEach(() => {
  vi.useFakeTimers()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('BronStatusMelding', () => {
  it('toont niets als alle bronnen live zijn', async () => {
    vi.stubGlobal('fetch', vi.fn(() => antwoord([])))
    await toon()
    expect(container.textContent).toBe('')
    expect(container.querySelectorAll('p')).toHaveLength(0)
  })

  it('houdt de live-regio altijd gemonteerd, leeg zolang er niets is, zodat een melding wordt voorgelezen', async () => {
    vi.stubGlobal('fetch', vi.fn(() => antwoord([])))
    await toon()
    const regio = container.querySelector('[role="status"]')
    expect(regio).not.toBeNull()
    expect(regio.getAttribute('aria-live')).toBe('polite')
  })

  it('noemt een bron die niet live is', async () => {
    vi.stubGlobal('fetch', vi.fn(() => antwoord([DUO])))
    await toon()
    expect(container.textContent).toContain(DUO.tekst)
  })

  it('toont één melding per bron die niet live is', async () => {
    const cbs = { ...DUO, bron: 'cbs', naam: 'CBS', tekst: 'CBS is op dit moment niet bereikbaar.' }
    vi.stubGlobal('fetch', vi.fn(() => antwoord([DUO, cbs])))
    await toon()
    expect(container.querySelectorAll('p')).toHaveLength(2)
  })

  it('vraagt het openbare eindpunt zonder inlog', async () => {
    const fetchMock = vi.fn(() => antwoord([]))
    vi.stubGlobal('fetch', fetchMock)
    await toon()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/bronstatus')
  })

  it('haalt de stand na een tijd opnieuw op en haalt de melding weg als de bron weer live is', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => antwoord([DUO]))
      .mockImplementation(() => antwoord([]))
    vi.stubGlobal('fetch', fetchMock)
    await toon()
    expect(container.textContent).toContain('DUO')
    await ververs()
    expect(container.textContent).toBe('')
  })

  it('haalt de stand opnieuw op zodra het netwerk terugkomt (herverbinden)', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => antwoord([]))
      .mockImplementation(() => antwoord([DUO]))
    vi.stubGlobal('fetch', fetchMock)
    await toon()
    expect(container.textContent).toBe('')
    await act(async () => {
      window.dispatchEvent(new Event('online'))
    })
    expect(container.textContent).toContain('DUO')
  })

  it('haalt de stand opnieuw op als de pagina weer zichtbaar wordt', async () => {
    const fetchMock = vi.fn(() => antwoord([]))
    vi.stubGlobal('fetch', fetchMock)
    await toon()
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('laat de laatst bekende stand staan als het eindpunt niet antwoordt', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => antwoord([DUO]))
      .mockImplementation(() => Promise.reject(new Error('offline')))
    vi.stubGlobal('fetch', fetchMock)
    await toon()
    await ververs()
    expect(container.textContent).toContain('DUO')
  })

  it('toont niets en crasht niet als het eindpunt een fout geeft', async () => {
    vi.stubGlobal('fetch', vi.fn(() => antwoord([DUO], false)))
    await toon()
    expect(container.textContent).toBe('')
  })

  it('toont niets bij een antwoord zonder lijst', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) })))
    await toon()
    expect(container.textContent).toBe('')
  })

  it('stopt met verversen als de component weg is', async () => {
    const fetchMock = vi.fn(() => antwoord([]))
    vi.stubGlobal('fetch', fetchMock)
    await toon()
    act(() => root.unmount())
    root = createRoot(container)
    await ververs()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
