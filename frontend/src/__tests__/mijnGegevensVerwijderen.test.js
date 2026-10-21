// @vitest-environment jsdom
// "Verwijder al mijn gegevens" in de instellingen (#646): de api-helper, de knop en de bevestigingsdialoog.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import MijnGegevensVerwijderen, { BEVESTIGWOORD, VERWIJDEREN_MISLUKT, isBevestigd } from '../components/MijnGegevensVerwijderen'
import SettingsModal from '../components/SettingsModal'
import { deleteMijnGegevens } from '../api'
import { onSessionEnded } from '../auth'
import { volgOpslag } from '../gesprekOpslag'
import {
  SESSION_DATA_KEYS, STORAGE_SETTINGS, STORAGE_ONBOARDED, STORAGE_TOKEN, STORAGE_USERINFO, STORAGE_MODEL, STORAGE_RECENT,
} from '../constants'

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
  act(() => root?.unmount())
  container?.remove()
  root = null
  container = null
  localStorage.clear()
  vi.unstubAllGlobals()
})

const LABEL = 'Verwijder al mijn gegevens'
const ZESMAAL_NUL = { conversations: 0, workbooks: 0, feedback: 0, algemene_feedback: 0, answer_feedback: 0, data_recipes: 0 }
const openKnop = () => document.querySelector('.mijn-gegevens-verwijderen-btn')
const dialoog = () => document.querySelector('[role="alertdialog"]')
const invoer = () => dialoog().querySelector('input')
const bevestigKnop = () => dialoog().querySelector('button[type="submit"]')
const knopMetTekst = tekst => [...dialoog().querySelectorAll('button')].find(b => b.textContent === tekst)
const fout = () => document.querySelector('.mijn-gegevens-verwijderen-fout')

function response(status, body = {}) {
  return { status, ok: status >= 200 && status < 300, json: async () => body }
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

// React tracks an input's value itself: set it through the native setter, then fire input.
async function typ(tekst) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(invoer(), tekst)
    invoer().dispatchEvent(new Event('input', { bubbles: true }))
  })
}

async function open() {
  openKnop().focus()
  await act(async () => { openKnop().click() })
  expect(dialoog()).not.toBeNull()
}

async function toets(key, opties = {}) {
  await act(async () => {
    document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...opties }))
  })
}

// A click in a browser also focuses the button; jsdom's click() does not.
async function bevestig(tekst = BEVESTIGWOORD) {
  await typ(tekst)
  bevestigKnop().focus()
  await act(async () => { bevestigKnop().click() })
}

// Everything a logged-in browser holds: what goes on success, and what stays (model, recently viewed).
function vulLocalStorage() {
  for (const key of SESSION_DATA_KEYS) localStorage.setItem(key, `[${key}]`)
  localStorage.setItem(STORAGE_SETTINGS, '{"instelling":"Hogeschool Utrecht"}')
  localStorage.setItem(STORAGE_ONBOARDED, '1')
  localStorage.setItem(STORAGE_TOKEN, 'tok-1')
  localStorage.setItem(STORAGE_USERINFO, '{"name":"Anna"}')
  localStorage.setItem(STORAGE_MODEL, 'claude')
  localStorage.setItem(STORAGE_RECENT, '{"gesprekken":["c1"]}')
}
const opslag = () => Object.fromEntries(Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i)).map(k => [k, localStorage.getItem(k)]))

describe('deleteMijnGegevens', () => {
  it('sends DELETE /api/mijn-gegevens with the token and the fixed confirmation, and returns the counts', async () => {
    localStorage.setItem(STORAGE_TOKEN, 'tok-1')
    const fetchMock = vi.fn(async () => response(200, { ok: true, verwijderd: ZESMAAL_NUL }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(deleteMijnGegevens()).resolves.toEqual({ ok: true, verwijderd: ZESMAAL_NUL })

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, opties] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/mijn-gegevens')
    expect(opties.method).toBe('DELETE')
    expect(opties.headers.Authorization).toBe('Bearer tok-1')
    expect(opties.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(opties.body)).toEqual({ bevestig: 'verwijder' })
  })

  it('ends the session on a 401, like the other helpers', async () => {
    localStorage.setItem(STORAGE_TOKEN, 'tok-2')
    vi.stubGlobal('fetch', vi.fn(async () => response(401)))
    const ended = vi.fn()
    const off = onSessionEnded(ended)
    try {
      await expect(deleteMijnGegevens()).rejects.toMatchObject({ status: 401 })
    } finally {
      off()
    }
    expect(ended).toHaveBeenCalledOnce()
    expect(localStorage.getItem(STORAGE_TOKEN)).toBeNull()
  })
})

describe('isBevestigd', () => {
  it.each([['verwijder', true], ['Verwijder', true], [' VERWIJDER ', true], ['verwijde', false], ['verwijderen', false], ['', false]])(
    '%j is %s: trimmed and case-insensitive, as a phone keyboard capitalises',
    (tekst, verwacht) => { expect(isBevestigd(tekst)).toBe(verwacht) },
  )
})

describe('the dialog', () => {
  it('is a labelled and described alertdialog, with the focus in the confirmation field', async () => {
    await render(createElement(MijnGegevensVerwijderen, { onVerwijderd: vi.fn() }))
    expect(openKnop().textContent).toBe(LABEL)
    expect(openKnop().getAttribute('type')).toBe('button')
    expect(dialoog()).toBeNull()

    await open()

    const d = dialoog()
    expect(d.getAttribute('aria-modal')).toBe('true')
    expect(document.getElementById(d.getAttribute('aria-labelledby')).textContent).toBe('Al je gegevens verwijderen?')
    const uitleg = document.getElementById(d.getAttribute('aria-describedby')).textContent
    expect(uitleg).toContain('Dit kan niet ongedaan worden gemaakt')
    expect(document.activeElement).toBe(invoer())
    expect(invoer().getAttribute('autocapitalize')).toBe('off')
    expect(document.querySelector(`label[for="${invoer().id}"]`).textContent).toBe(`Typ ${BEVESTIGWOORD} om te bevestigen`)
    // In a portal, so a backdrop click does not reach the settings backdrop.
    expect(container.contains(d)).toBe(false)
  })

  it('says what goes, what stays elsewhere and who else loses work, and offers the export in place', async () => {
    await render(createElement(MijnGegevensVerwijderen, { onVerwijderd: vi.fn() }))
    await open()

    const uitleg = document.getElementById(dialoog().getAttribute('aria-describedby')).textContent
    for (const tekst of [
      'gesprekken', 'rapporten en dashboards', 'al je feedback', 'per antwoord', 'datarecepten',
      'niet ongedaan', 'kopie in deze browser', 'ander apparaat', 'tot je daar uitlogt', 'samen met anderen',
    ]) expect(uitleg).toContain(tekst)
    const exportKnop = dialoog().querySelector('.mijn-gegevens-export-btn')
    expect(exportKnop.textContent).toBe('Exporteer al mijn gegevens')
    expect(dialoog().textContent).toContain('Bewaar eerst een kopie')
  })

  it('keeps Tab inside the dialog', async () => {
    await render(createElement(MijnGegevensVerwijderen, { onVerwijderd: vi.fn() }))
    await open()
    const eerste = dialoog().querySelector('.mijn-gegevens-export-btn')
    const laatste = knopMetTekst('Annuleren') // the confirm button is disabled, so not focusable yet

    laatste.focus()
    await toets('Tab')
    expect(document.activeElement).toBe(eerste)
    await toets('Tab', { shiftKey: true })
    expect(document.activeElement).toBe(laatste)
  })

  it.each([
    ['Escape', () => toets('Escape')],
    ['Annuleren', () => act(async () => { knopMetTekst('Annuleren').click() })],
    ['a backdrop click', () => act(async () => { document.querySelector('.mijn-gegevens-verwijderen-overlay').click() })],
  ])('%s closes it and gives the focus back to the button that opened it', async (_, sluit) => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    await render(createElement(MijnGegevensVerwijderen, { onVerwijderd: vi.fn() }))
    await open()

    await sluit()

    expect(dialoog()).toBeNull()
    expect(document.activeElement).toBe(openKnop())
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('a click inside the dialog does not close it', async () => {
    await render(createElement(MijnGegevensVerwijderen, { onVerwijderd: vi.fn() }))
    await open()
    await act(async () => { dialoog().querySelector('p').click() })
    expect(dialoog()).not.toBeNull()
  })
})

describe('inside the settings dialog', () => {
  const modal = props => createElement(SettingsModal, { settings: {}, onSave: vi.fn(), onClose: vi.fn(), onLogout: vi.fn(), onGegevensVerwijderd: vi.fn(), ...props })

  it('a backdrop click and Escape close only this dialog, not the settings', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response(200, [])))
    const onClose = vi.fn()
    await render(modal({ onClose }))

    await open()
    await act(async () => { document.querySelector('.mijn-gegevens-verwijderen-overlay').click() })
    expect(dialoog()).toBeNull()
    expect(container.querySelector('.settings-modal')).not.toBeNull()

    await open()
    await toets('Escape')
    expect(dialoog()).toBeNull()

    expect(onClose).not.toHaveBeenCalled()
  })
})

describe('confirming', () => {
  it('keeps the button disabled and sends nothing until the field says verwijder', async () => {
    const verwijder = vi.fn(async () => ({ ok: true, verwijderd: ZESMAAL_NUL }))
    await render(createElement(MijnGegevensVerwijderen, { onVerwijderd: vi.fn(), verwijder }))
    await open()
    expect(bevestigKnop().textContent).toBe('Definitief verwijderen')
    expect(bevestigKnop().disabled).toBe(true)

    for (const tekst of ['verwijde', 'ja', 'verwijderen']) {
      await typ(tekst)
      expect(bevestigKnop().disabled).toBe(true)
      await act(async () => { bevestigKnop().click() })
      await act(async () => { dialoog().requestSubmit() })
    }
    expect(verwijder).not.toHaveBeenCalled()

    await typ('Verwijder ')
    expect(bevestigKnop().disabled).toBe(false)
  })

  it('submits with Enter in the field: the field and the submit button share one form', async () => {
    const verwijder = vi.fn(async () => ({ ok: true, verwijderd: ZESMAAL_NUL }))
    const onVerwijderd = vi.fn()
    await render(createElement(MijnGegevensVerwijderen, { onVerwijderd, verwijder }))
    await open()
    await typ(BEVESTIGWOORD)

    // jsdom does no implicit submission; a browser submits the field's form on Enter (checked in the MR).
    expect(invoer().form).toBe(dialoog())
    expect(bevestigKnop().form).toBe(dialoog())
    await act(async () => { invoer().form.requestSubmit() })

    expect(verwijder).toHaveBeenCalledOnce()
    expect(onVerwijderd).toHaveBeenCalledWith({ ok: true, verwijderd: ZESMAAL_NUL })
  })

  it('sends the fixed confirmation through the real helper, whatever the capitals typed', async () => {
    localStorage.setItem(STORAGE_TOKEN, 'tok-1')
    const fetchMock = vi.fn(async () => response(200, { ok: true, verwijderd: ZESMAAL_NUL }))
    vi.stubGlobal('fetch', fetchMock)
    const onVerwijderd = vi.fn()
    await render(createElement(MijnGegevensVerwijderen, { onVerwijderd }))
    await open()

    await bevestig('VERWIJDER')

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ bevestig: 'verwijder' })
    expect(onVerwijderd).toHaveBeenCalledOnce()
  })

  it('waits for a conversation save under way before it sends the DELETE', async () => {
    const opslaan = deferred()
    volgOpslag(opslaan.promise)
    const verwijder = vi.fn(async () => ({ ok: true, verwijderd: ZESMAAL_NUL }))
    await render(createElement(MijnGegevensVerwijderen, { onVerwijderd: vi.fn(), verwijder }))
    await open()

    await bevestig()
    expect(verwijder).not.toHaveBeenCalled()

    await act(async () => { opslaan.resolve() })
    expect(verwijder).toHaveBeenCalledOnce()
  })

  it('while the request runs, nothing closes the dialog and nothing is sent twice', async () => {
    const lopend = deferred()
    const verwijder = vi.fn(() => lopend.promise)
    const onVerwijderd = vi.fn()
    await render(createElement(MijnGegevensVerwijderen, { onVerwijderd, verwijder }))
    await open()
    await bevestig()

    expect(bevestigKnop().textContent).toBe('Bezig met verwijderen…')
    expect(bevestigKnop().getAttribute('aria-busy')).toBe('true')
    expect(bevestigKnop().disabled).toBe(true)
    expect(knopMetTekst('Annuleren').disabled).toBe(true)
    await toets('Escape')
    await act(async () => { document.querySelector('.mijn-gegevens-verwijderen-overlay').click() })
    await act(async () => { dialoog().requestSubmit() })
    expect(dialoog()).not.toBeNull()
    expect(verwijder).toHaveBeenCalledOnce()

    await act(async () => { lopend.resolve({ ok: true, verwijderd: ZESMAAL_NUL }) })
    expect(onVerwijderd).toHaveBeenCalledOnce()
  })
})

describe('on failure', () => {
  it.each([
    ['a 500', async () => response(500, { detail: 'boom' }), ['API 500', 'boom']],
    ['a 404', async () => response(404, { detail: 'Zonder inloggen is er geen eigen account om te verwijderen.' }), ['API 404', 'Zonder inloggen']],
    ['a network error', async () => { throw new TypeError('Failed to fetch') }, ['Failed to fetch']],
  ])('on %s shows a fixed Dutch sentence, keeps dialog, field and storage, and a second attempt works', async (_, eerste, ruw) => {
    vulLocalStorage()
    const fetchMock = vi.fn(eerste)
    vi.stubGlobal('fetch', fetchMock)
    const onVerwijderd = vi.fn()
    await render(createElement(MijnGegevensVerwijderen, { onVerwijderd }))
    await open()
    const voor = opslag()

    await bevestig()

    expect(fout().getAttribute('role')).toBe('alert')
    expect(fout().textContent).toBe(VERWIJDEREN_MISLUKT)
    for (const tekst of ruw) expect(document.body.textContent).not.toContain(tekst)
    expect(dialoog()).not.toBeNull()
    expect(invoer().value).toBe(BEVESTIGWOORD)
    expect(opslag()).toEqual(voor)
    expect(onVerwijderd).not.toHaveBeenCalled()
    expect(bevestigKnop().disabled).toBe(false)
    expect(document.activeElement).toBe(bevestigKnop())

    fetchMock.mockImplementation(async () => response(200, { ok: true, verwijderd: ZESMAAL_NUL }))
    await act(async () => { bevestigKnop().click() })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fout()).toBeNull()
    expect(onVerwijderd).toHaveBeenCalledWith({ ok: true, verwijderd: ZESMAAL_NUL })
  })
})

describe('CSS', () => {
  const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
  const regel = selector => {
    const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return new RegExp(`(?:^|\\})\\s*${escaped}\\s*\\{([^}]*)\\}`).exec(css)?.[1]
  }

  it('gives the button and every dialog button 44px on every screen, outside a media query', () => {
    expect(regel('.mijn-gegevens-verwijderen-btn')).toMatch(/min-height:\s*var\(--tap-min\)/)
    expect(regel('.mijn-gegevens-verwijderen-acties button')).toMatch(/min-height:\s*var\(--tap-min\)/)
    expect(css).toMatch(/--tap-min:\s*44px/)
  })

  it('gives Annuleren a text colour of its own: a button does not inherit one, and it was black in dark mode', () => {
    expect(regel('.mijn-gegevens-verwijderen-acties .confirm-cancel')).toMatch(/color:\s*var\(--gray-700\)/)
  })

  it('gives the field 16px on every screen and stacks the dialog above the settings (2000)', () => {
    expect(regel('.mijn-gegevens-verwijderen-invoer')).toMatch(/font-size:\s*16px/)
    expect(regel('.mijn-gegevens-verwijderen-overlay')).toMatch(/z-index:\s*2100/)
  })
})
