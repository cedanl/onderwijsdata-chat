// @vitest-environment jsdom
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { fetchDashboardData } from '../api'
import { onSessionEnded } from '../auth'
import { STORAGE_TOKEN } from '../constants'
import { useRegioDashboardData } from '../components/dashboards/shared/hooks'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const antwoord = (status, body) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

let fetchMock

beforeEach(() => {
  localStorage.clear()
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

// With login on the dashboard routes want the token (#636); a bare fetch broke the dashboards.
describe('fetchDashboardData', () => {
  it('sends the token as a bearer header', async () => {
    localStorage.setItem(STORAGE_TOKEN, 'tok-1')
    fetchMock.mockResolvedValue(antwoord(200, { ingeschrevenen: {} }))

    const data = await fetchDashboardData('/api/dashboard/regio', 'Hogeschool Utrecht')

    expect(data).toEqual({ ingeschrevenen: {} })
    const [path, options] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/dashboard/regio?instelling=Hogeschool+Utrecht')
    expect(options.headers.Authorization).toBe('Bearer tok-1')
  })

  it('sends no Authorization header without a token (login off)', async () => {
    fetchMock.mockResolvedValue(antwoord(200, {}))

    await fetchDashboardData('/api/dashboard/regio', 'VU')

    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('Authorization')
  })

  it('passes the abort signal on', async () => {
    fetchMock.mockResolvedValue(antwoord(200, {}))
    const ac = new AbortController()

    await fetchDashboardData('/api/dashboard/regio', 'VU', { signal: ac.signal })

    expect(fetchMock.mock.calls[0][1].signal).toBe(ac.signal)
  })

  it('ends the session on a 401 for the token it sent', async () => {
    localStorage.setItem(STORAGE_TOKEN, 'tok-1')
    fetchMock.mockResolvedValue(antwoord(401, { detail: 'Niet geautoriseerd' }))
    const ended = vi.fn()
    const stop = onSessionEnded(ended)

    await expect(fetchDashboardData('/api/dashboard/regio', 'VU')).rejects.toMatchObject({ status: 401 })

    stop()
    expect(ended).toHaveBeenCalledOnce()
    expect(localStorage.getItem(STORAGE_TOKEN)).toBeNull()
  })

  it('reports the server error when dashboards are off', async () => {
    fetchMock.mockResolvedValue(antwoord(403, { error: 'Dashboards zijn niet beschikbaar' }))

    await expect(fetchDashboardData('/api/dashboard/regio', 'VU'))
      .rejects.toMatchObject({ status: 403, message: 'Dashboards zijn niet beschikbaar' })
  })
})

describe('dashboard data hook', () => {
  let root
  let container
  let state

  function Probe({ instelling }) {
    state = useRegioDashboardData(instelling)
    return null
  }

  async function mount(instelling) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => { root.render(createElement(Probe, { instelling })) })
  }

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it('loads the data with the token', async () => {
    localStorage.setItem(STORAGE_TOKEN, 'tok-2')
    fetchMock.mockResolvedValue(antwoord(200, { laatste_jaar: 2025 }))

    await mount('VU')

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer tok-2')
    expect(state).toEqual({ data: { laatste_jaar: 2025 }, loading: false, error: null })
  })

  it('shows an error instead of data when the session has ended', async () => {
    localStorage.setItem(STORAGE_TOKEN, 'tok-3')
    fetchMock.mockResolvedValue(antwoord(401, { detail: 'Niet geautoriseerd' }))

    await mount('VU')

    expect(state).toEqual({ data: null, loading: false, error: 'Unauthorized' })
    expect(localStorage.getItem(STORAGE_TOKEN)).toBeNull()
  })
})
