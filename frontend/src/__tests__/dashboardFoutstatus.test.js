// @vitest-environment jsdom
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { dashboardFout, DASHBOARD_TIMEOUT_MS, useRegioDashboardData } from '../components/dashboards/shared/hooks'
import { DashboardShell, NietGeladen, gatenVan } from '../components/dashboards/shared/shell'
import { InlineDashboardArbeidsmarkt } from '../components/dashboards/arbeidsmarkt-consolidated'

vi.mock('react-chartjs-2', () => ({ Bar: () => null, Line: () => null }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true

// A failed or slow dashboard load said "niet gevonden", showed the raw "API 500" or "Failed to fetch", and had no
// way to try again (#901). The server now tells a source outage from an unknown name; the frontend shows that.

const antwoord = (status, body) => ({ status, ok: status >= 200 && status < 300, json: async () => body })
const fout = (status, message) => Object.assign(new Error(message), { status })

let fetchMock
let root
let container

beforeEach(() => {
  localStorage.clear()
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
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

async function render(element) {
  await act(async () => { root.render(element) })
}

const knop = tekst => [...container.querySelectorAll('button')].find(b => b.textContent === tekst)

describe('dashboardFout', () => {
  it('passes the server text on for a source outage, the busy queue and the time limit, with a retry', () => {
    const melding = 'De DUO-data is nu niet beschikbaar. Probeer het over een paar minuten opnieuw.'
    expect(dashboardFout(fout(503, melding))).toEqual({ melding, herstelbaar: true })
    expect(dashboardFout(fout(504, 'Het dashboard kwam niet binnen 90 seconden af.')).herstelbaar).toBe(true)
  })

  it('never shows the raw status or the browser error', () => {
    for (const e of [fout(500, 'API 500'), fout(502, 'API 502'), new TypeError('Failed to fetch')]) {
      const { melding, herstelbaar } = dashboardFout(e)
      expect(melding).not.toMatch(/API \d|Failed to fetch/)
      expect(herstelbaar).toBe(true)
    }
    expect(dashboardFout(fout(503, 'API 503')).melding).not.toMatch(/API/)
  })

  it('offers no retry where retrying cannot help', () => {
    expect(dashboardFout(fout(401, 'Unauthorized')).herstelbaar).toBe(false)
    expect(dashboardFout(fout(403, 'Dashboards zijn niet beschikbaar'))).toEqual({
      melding: 'Dashboards zijn niet beschikbaar', herstelbaar: false,
    })
  })

  it('says the dashboard took too long when the browser stopped waiting', () => {
    expect(dashboardFout(new DOMException('aborted', 'AbortError'), true).melding).toMatch(/niet op tijd/)
  })
})

describe('dashboard data hook', () => {
  let state
  function Probe({ instelling }) {
    state = useRegioDashboardData(instelling)
    return null
  }

  it('tries again on opnieuw, and then shows the data', async () => {
    fetchMock
      .mockResolvedValueOnce(antwoord(503, { error: 'De DUO-data is nu niet beschikbaar.' }))
      .mockResolvedValueOnce(antwoord(200, { gevonden: true }))
    await render(createElement(Probe, { instelling: 'HU' }))
    expect(state.error).toEqual({ melding: 'De DUO-data is nu niet beschikbaar.', herstelbaar: true })

    await act(async () => { state.opnieuw() })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(state.data).toEqual({ gevonden: true })
    expect(state.error).toBeNull()
  })

  it('stops waiting after the time limit', async () => {
    vi.useFakeTimers()
    fetchMock.mockImplementation((path, { signal }) => new Promise((resolve, reject) => {
      signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    }))
    await render(createElement(Probe, { instelling: 'HU' }))
    expect(state.loading).toBe(true)

    await act(async () => { vi.advanceTimersByTime(DASHBOARD_TIMEOUT_MS) })

    expect(state.loading).toBe(false)
    expect(state.error.melding).toMatch(/niet op tijd/)
  })
})

describe('DashboardShell', () => {
  it('shows a source outage with a retry button, not "niet gevonden"', async () => {
    const onOpnieuw = vi.fn()
    const error = { melding: 'De DUO-data is nu niet beschikbaar.', herstelbaar: true }
    await render(createElement(DashboardShell, { instelling: 'HU', loading: false, data: null, error, onOpnieuw }))

    expect(container.querySelector('[role="alert"]').textContent).toContain('De DUO-data is nu niet beschikbaar.')
    expect(container.textContent).not.toContain('niet gevonden')
    await act(async () => { knop('Opnieuw proberen').click() })
    expect(onOpnieuw).toHaveBeenCalledOnce()
  })

  it('names the suggestions for an unknown name, or why there are none (#929)', async () => {
    const met = { gevonden: false, beschikbare_instellingen: ['Hogeschool Utrecht'] }
    await render(createElement(DashboardShell, { instelling: 'Hogeschool Utrect', data: met }))
    expect(container.textContent).toContain('Bedoel je misschien: Hogeschool Utrecht?')

    const reden = 'Geen instellingsnaam lijkt hierop. Zoek op de naam, een afkorting of de instellingscode (BRIN).'
    const zonder = { gevonden: false, beschikbare_instellingen: [], geen_suggesties: reden }
    await render(createElement(DashboardShell, { instelling: 'XYZ', data: zonder }))
    expect(container.textContent).toContain(reden)
    expect(container.textContent).not.toContain('Bedoel je')
  })

  it('has no retry button for an error that retrying does not solve', async () => {
    const error = { melding: 'Dashboards zijn niet beschikbaar', herstelbaar: false }
    await render(createElement(DashboardShell, { instelling: 'HU', data: null, error, onOpnieuw: () => {} }))

    expect(knop('Opnieuw proberen')).toBeUndefined()
  })
})

describe('NietGeladen', () => {
  it('names each part that did not load and why', async () => {
    const onderdelen = [{ onderdeel: 'Vacatures (UWV)', bron: 'UWV', reden: 'de bron was niet bereikbaar' }]
    await render(createElement(NietGeladen, { onderdelen, onOpnieuw: () => {} }))

    expect(container.textContent).toContain('Vacatures (UWV): de bron was niet bereikbaar.')
    expect(knop('Opnieuw proberen')).toBeDefined()
  })

  it('shows nothing without gaps', async () => {
    await render(createElement(NietGeladen, { onderdelen: [] }))

    expect(container.innerHTML).toBe('')
  })

  it('merges the gaps of two payloads once each, limited to the sources a dashboard shows', () => {
    const uwv = { onderdeel: 'Vacatures (UWV)', bron: 'UWV', reden: 'x' }
    const kaart = { onderdeel: 'Kaart', bron: 'DUO', reden: 'y' }

    expect(gatenVan([{ niet_beschikbaar: [uwv] }, { niet_beschikbaar: [uwv, kaart] }])).toEqual([uwv, kaart])
    expect(gatenVan([{ niet_beschikbaar: [uwv, kaart] }, null], ['UWV'])).toEqual([uwv])
  })
})

describe('arbeidsmarkt dashboard: the second load (regio)', () => {
  const MATCH = { gevonden: true, type: 'ho', provincie: 'Utrecht', gediplomeerden_per_sector: {}, vacatures_per_sector: {} }

  function routes(regio) {
    fetchMock.mockImplementation(path => (path.startsWith('/api/dashboard/regio') ? regio() : Promise.resolve(antwoord(200, MATCH))))
  }

  it('shows a loading block while regio loads, not "Geen vacaturegegevens"', async () => {
    routes(() => new Promise(() => {}))
    await render(createElement(InlineDashboardArbeidsmarkt, { instelling: 'Hogeschool Utrecht' }))

    expect(container.textContent).not.toContain('Geen vacaturegegevens')
    expect(container.querySelector('[aria-label="Vacatures en prognoses in de regio laden"]')).not.toBeNull()
  })

  it('shows the error with a retry when regio fails, and loads it again', async () => {
    let regio = () => Promise.resolve(antwoord(503, { error: 'De DUO-data is nu niet beschikbaar.' }))
    routes(() => regio())
    await render(createElement(InlineDashboardArbeidsmarkt, { instelling: 'Hogeschool Utrecht' }))

    expect(container.textContent).toContain('Vacatures en prognoses in de regio kon niet worden geladen.')
    expect(container.textContent).not.toContain('Geen vacaturegegevens')

    regio = () => Promise.resolve(antwoord(200, { gevonden: true, provincie: 'Utrecht', vacatureaanbod: {} }))
    await act(async () => { knop('Opnieuw proberen').click() })

    expect(container.textContent).not.toContain('kon niet worden geladen')
    expect(container.textContent).toContain('Geen vacaturegegevens')
  })

  it('names the UWV gap of the regio payload, not its DUO gaps', async () => {
    const gaten = [
      { onderdeel: 'Vacatures (UWV)', bron: 'UWV', reden: 'de bron was niet bereikbaar' },
      { onderdeel: 'Kaart', bron: 'DUO', reden: 'de data van de bron kon niet worden verwerkt' },
    ]
    routes(() => Promise.resolve(antwoord(200, { gevonden: true, niet_beschikbaar: gaten })))
    await render(createElement(InlineDashboardArbeidsmarkt, { instelling: 'Hogeschool Utrecht' }))

    expect(container.textContent).toContain('Vacatures (UWV): de bron was niet bereikbaar.')
    expect(container.textContent).not.toContain('Kaart:')
  })
})
