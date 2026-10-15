// @vitest-environment jsdom
// #572: de privacy-informatie opent als popup op elke plek die eerder naar /privacy linkte, met
// dezelfde tekst als de pagina. Ook in het instellingenvenster, waar twee dialogen op elkaar liggen.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import PrivacyPage, { PRIVACY_KOPJES } from '../pages/PrivacyPage'
import PrivacyModal from '../components/PrivacyModal'
import PrivacyLink from '../components/PrivacyLink'
import LoginPage from '../pages/LoginPage'
import SettingsModal from '../components/SettingsModal'
import HomePage from '../pages/HomePage'
import ChatPage from '../pages/ChatPage'

// Keep the pages off the network and away from heavy children: only the privacy button matters here.
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))
vi.mock('../api', () => {
  const pending = () => new Promise(() => {})
  return {
    fetchCatalogCounts: pending,
    fetchConversations: pending,
    fetchSettingsConfig: pending,
    putConversation: pending,
    renameConversationApi: pending,
    deleteConversationApi: pending,
    fetchAnswerFeedback: pending,
    postAnswerFeedback: pending,
  }
})
vi.mock('../components/ScrollToBottom', () => ({ default: () => null }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [], busy: false, rejectedDraft: null, clearRejectedDraft: vi.fn(), thinking: false, toasts: [],
    connected: true, resetting: false, historyDataKeys: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: vi.fn(), sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver ??= class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

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
})

const privacyDialog = () => document.querySelector('[role="dialog"][aria-label="Privacy-informatie"]')
const settingsDialog = () => document.querySelector('.settings-modal')
const kopjes = dialog => [...dialog.querySelectorAll('h2')].map(h => h.textContent)
const privacyButton = name => [...container.querySelectorAll('button')].find(b => b.textContent === name)
const press = (key, opts = {}) =>
  act(async () => { document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...opts })) })
const closeButton = () => privacyDialog().querySelector('button[aria-label="Sluiten"]')

async function openFrom(button) {
  button.focus()
  await act(async () => { button.click() })
}

const HOSTS = [
  ['the home page footer', () => createElement(MemoryRouter, null, createElement(HomePage)), 'Privacy'],
  ['the chat disclaimer', () => createElement(MemoryRouter, null, createElement(ChatPage, { settings: {}, user: 'gast' })), 'Privacy-informatie'],
  ['the login page, without a session', () => createElement(LoginPage, { onLogin: vi.fn(), oidcEnabled: false }), 'Privacy-informatie'],
  ['the settings dialog', () => createElement(SettingsModal, { settings: {}, onSave: vi.fn(), onClose: vi.fn() }), 'Privacy-informatie'],
]

describe.each(HOSTS)('the privacy button on %s', (_, element, name) => {
  it('opens the privacy popup with every section instead of linking to /privacy', async () => {
    await render(element())
    expect(container.querySelector('a[href="/privacy"]')).toBeNull()
    const button = privacyButton(name)
    expect(button.getAttribute('type')).toBe('button')
    expect(privacyDialog()).toBeNull()

    await openFrom(button)

    expect(privacyDialog().getAttribute('aria-modal')).toBe('true')
    expect(kopjes(privacyDialog())).toEqual(PRIVACY_KOPJES)
  })

  it('closes on Escape and gives focus back to the button', async () => {
    await render(element())
    const button = privacyButton(name)
    await openFrom(button)
    await press('Escape')
    expect(privacyDialog()).toBeNull()
    expect(document.activeElement).toBe(button)
  })
})

describe('PrivacyLink', () => {
  async function open() {
    await render(createElement(PrivacyLink))
    const button = privacyButton('Privacy-informatie')
    await openFrom(button)
    return button
  }

  it('moves focus into the popup', async () => {
    await open()
    expect(document.activeElement).toBe(closeButton())
  })

  it('closes with the close button and gives focus back', async () => {
    const button = await open()
    await act(async () => { closeButton().click() })
    expect(privacyDialog()).toBeNull()
    expect(document.activeElement).toBe(button)
  })

  it('closes on a click on the backdrop, not on a click in the text', async () => {
    await open()
    await act(async () => { privacyDialog().querySelector('h2').click() })
    expect(privacyDialog()).not.toBeNull()
    await act(async () => { privacyDialog().click() })
    expect(privacyDialog()).toBeNull()
  })

  it('keeps Tab inside the popup', async () => {
    await open()
    await press('Tab')
    expect(privacyDialog().contains(document.activeElement)).toBe(true)
    await press('Tab', { shiftKey: true })
    expect(privacyDialog().contains(document.activeElement)).toBe(true)
  })

  it('renders the popup outside the host, so it stacks above it', async () => {
    await open()
    expect(container.contains(privacyDialog())).toBe(false)
    expect(privacyDialog().classList.contains('modal-overlay--privacy')).toBe(true)
  })
})

describe('the privacy popup inside the settings dialog', () => {
  async function openInSettings(props = {}) {
    const onClose = vi.fn()
    await render(createElement(SettingsModal, { settings: {}, onSave: vi.fn(), onClose, ...props }))
    const button = privacyButton('Privacy-informatie')
    await openFrom(button)
    return { onClose, button }
  }

  it('Escape closes only the popup; a second Escape closes settings', async () => {
    const { onClose, button } = await openInSettings()
    await press('Escape')
    expect(privacyDialog()).toBeNull()
    expect(onClose).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(button)
    await press('Escape')
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('a backdrop click closes only the popup', async () => {
    const { onClose } = await openInSettings()
    await act(async () => { privacyDialog().click() })
    expect(privacyDialog()).toBeNull()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('Tab stays in the popup, not in settings', async () => {
    await openInSettings()
    for (const shiftKey of [false, true, false]) {
      await press('Tab', { shiftKey })
      expect(privacyDialog().contains(document.activeElement)).toBe(true)
    }
    expect(settingsDialog().contains(document.activeElement)).toBe(false)
  })

  it('works the same during onboarding', async () => {
    const { onClose } = await openInSettings({ isOnboarding: true })
    expect(kopjes(privacyDialog())).toEqual(PRIVACY_KOPJES)
    await press('Escape')
    expect(privacyDialog()).toBeNull()
    expect(onClose).not.toHaveBeenCalled()
  })
})

describe('one privacy text', () => {
  it('the popup and the page show the same text', async () => {
    await render(createElement(PrivacyPage))
    const page = container.querySelector('.privacy-text').innerHTML
    act(() => root.unmount())
    container.remove()

    await render(createElement(PrivacyModal, { onClose: vi.fn() }))
    expect(privacyDialog().querySelector('.privacy-text').innerHTML).toBe(page)
  })

  it('the text exists once in the source', () => {
    const src = join(__dirname, '..')
    const files = readdirSync(src, { recursive: true })
      .filter(f => /\.jsx?$/.test(f) && !f.includes('__tests__'))
      .filter(f => readFileSync(join(src, f), 'utf8').includes('Verwerkersovereenkomst met de AI-aanbieder'))
    expect(files).toEqual([join('components', 'PrivacyInhoud.jsx')])
  })
})

describe('privacy popup styles', () => {
  const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')

  it('stacks above the settings dialog (z-index 2000)', () => {
    const zIndex = Number(/\.modal-overlay--privacy\s*\{[^}]*z-index:\s*(\d+)/.exec(css)[1])
    expect(zIndex).toBeGreaterThan(2000)
  })

  it('gives the text buttons a 44px tap target on touch screens', () => {
    const touch = css.slice(css.indexOf('@media (pointer: coarse), (max-width: 1024px)'))
    const rule = /([^{}]*\.privacy-link[^{}]*)\{([^}]*)\}/.exec(touch)
    expect(rule[2]).toMatch(/min-height:\s*var\(--tap-min\)/)
  })
})
