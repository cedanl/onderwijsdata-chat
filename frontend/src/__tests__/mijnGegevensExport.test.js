// @vitest-environment jsdom
// "Exporteer al mijn gegevens" in de instellingen (#645): de knop, zijn toestanden en de api-helper.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import MijnGegevensExport, { EXPORT_GELUKT, EXPORT_MISLUKT } from '../components/MijnGegevensExport'
import SettingsModal from '../components/SettingsModal'
import { downloadMijnGegevens } from '../api'
import { onSessionEnded } from '../auth'
import { STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  localStorage.clear()
  vi.unstubAllGlobals()
})

const LABEL = 'Exporteer al mijn gegevens'
const exportButton = () => container.querySelector('.mijn-gegevens-export-btn')
const buttonByText = text => [...container.querySelectorAll('button')].find(b => b.textContent === text)
const alert = () => container.querySelector('[role="alert"]')

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

function response(status, { body = '{}', headers = {} } = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: new globalThis.Headers(headers),
    json: async () => JSON.parse(body),
    blob: async () => new Blob([body], { type: 'application/json' }),
  }
}

describe('MijnGegevensExport', () => {
  it('calls the export helper once; busy and disabled while it runs, then saved and announced', async () => {
    const pending = deferred()
    const download = vi.fn(() => pending.promise)
    const save = vi.fn()
    await render(createElement(MijnGegevensExport, { download, save }))
    expect(exportButton().textContent).toBe(LABEL)
    expect(exportButton().getAttribute('aria-busy')).toBe('false')

    await act(async () => { exportButton().click() })
    expect(download).toHaveBeenCalledOnce()
    expect(download).toHaveBeenCalledWith({ save })
    expect(exportButton().getAttribute('aria-busy')).toBe('true')
    expect(exportButton().disabled).toBe(true)

    await act(async () => { exportButton().click() })
    expect(download).toHaveBeenCalledOnce()

    await act(async () => { pending.resolve() })
    expect(exportButton().getAttribute('aria-busy')).toBe('false')
    expect(exportButton().disabled).toBe(false)
    expect(exportButton().textContent).toBe(LABEL)
    expect(container.querySelector('[role="status"]').textContent).toBe(EXPORT_GELUKT)
    expect(alert()).toBeNull()
  })

  it('gives the focus back to the button when the export is done', async () => {
    const pending = deferred()
    await render(createElement(MijnGegevensExport, { download: () => pending.promise }))
    exportButton().focus()
    await act(async () => { exportButton().click() })
    await act(async () => { pending.resolve() })
    expect(document.activeElement).toBe(exportButton())
  })

  it('saves the file the server sends, under its name, through the real helper', async () => {
    localStorage.setItem(STORAGE_TOKEN, 'tok-1')
    const fetchMock = vi.fn(async () => response(200, {
      body: '{"schema_version": 1}',
      headers: { 'Content-Disposition': 'attachment; filename="openedudata-mijn-gegevens-2026-10-20.json"' },
    }))
    vi.stubGlobal('fetch', fetchMock)
    const save = vi.fn()
    await render(createElement(MijnGegevensExport, { save }))

    await act(async () => { exportButton().click() })

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledWith('/api/mijn-gegevens/export', { headers: { Authorization: 'Bearer tok-1' } })
    expect(save).toHaveBeenCalledOnce()
    const [blob, filename] = save.mock.calls[0]
    expect(filename).toBe('openedudata-mijn-gegevens-2026-10-20.json')
    expect(await blob.text()).toBe('{"schema_version": 1}')
    expect(alert()).toBeNull()
  })

  it.each([
    ['a 500', async () => response(500, { body: '{"detail": "boom"}' }), ['API 500', 'boom']],
    ['a network error', async () => { throw new TypeError('Failed to fetch') }, ['Failed to fetch']],
    ['a body cut off halfway', async () => ({ ...response(200), blob: async () => { throw new TypeError('network error') } }), ['network error']],
  ])('on %s shows a Dutch message, without the raw error, and saves nothing', async (_, fetchImpl, raw) => {
    vi.stubGlobal('fetch', vi.fn(fetchImpl))
    const save = vi.fn()
    await render(createElement(MijnGegevensExport, { save }))

    await act(async () => { exportButton().click() })

    expect(alert().textContent).toBe(EXPORT_MISLUKT)
    for (const tekst of raw) expect(container.textContent).not.toContain(tekst)
    expect(save).not.toHaveBeenCalled()
    expect(exportButton().disabled).toBe(false)
  })

  it('a new attempt clears the earlier message', async () => {
    const download = vi.fn().mockRejectedValueOnce(new Error('API 500')).mockResolvedValueOnce()
    await render(createElement(MijnGegevensExport, { download }))
    await act(async () => { exportButton().click() })
    expect(alert()).not.toBeNull()
    await act(async () => { exportButton().click() })
    expect(alert()).toBeNull()
    expect(container.querySelector('[role="status"]').textContent).toBe(EXPORT_GELUKT)
  })
})

describe('downloadMijnGegevens', () => {
  it('ends the session on a 401, like the other helpers', async () => {
    localStorage.setItem(STORAGE_TOKEN, 'tok-2')
    vi.stubGlobal('fetch', vi.fn(async () => response(401)))
    const ended = vi.fn()
    const off = onSessionEnded(ended)
    const save = vi.fn()
    try {
      await expect(downloadMijnGegevens({ save })).rejects.toMatchObject({ status: 401 })
    } finally {
      off()
    }
    expect(ended).toHaveBeenCalledOnce()
    expect(localStorage.getItem(STORAGE_TOKEN)).toBeNull()
    expect(save).not.toHaveBeenCalled()
  })
})

describe('SettingsModal: Exporteer al mijn gegevens', () => {
  const modal = props => createElement(SettingsModal, { settings: {}, onSave: vi.fn(), onClose: vi.fn(), ...props })

  it('sits directly above Uitloggen, as a native button the keyboard reaches', async () => {
    await render(modal({ onLogout: vi.fn() }))
    const button = exportButton()
    expect(button.tagName).toBe('BUTTON')
    expect(button.getAttribute('type')).toBe('button')
    expect(button.hasAttribute('tabindex')).toBe(false)
    expect(button.parentElement.nextElementSibling).toBe(buttonByText('Uitloggen'))
    button.focus()
    expect(document.activeElement).toBe(button)
  })

  it('is offered without login too, when there is no Uitloggen', async () => {
    await render(modal({ onLogout: null }))
    expect(exportButton().textContent).toBe(LABEL)
  })

  it('is not offered during onboarding, like Uitloggen', async () => {
    await render(modal({ onLogout: vi.fn(), isOnboarding: true }))
    expect(exportButton()).toBeNull()
    expect(container.textContent).not.toContain(LABEL)
  })
})

describe('tap target', () => {
  const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')

  it('is 44px high on every screen, not only on touch screens', () => {
    const rule = /(?:^|\})\s*\.mijn-gegevens-export-btn\s*\{([^}]*)\}/.exec(css)
    expect(rule).not.toBeNull()
    expect(rule[1]).toMatch(/min-height:\s*var\(--tap-min\)/)
    expect(css).toMatch(/--tap-min:\s*44px/)
  })
})
