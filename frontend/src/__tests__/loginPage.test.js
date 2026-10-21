// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('../auth', () => ({ login: vi.fn() }))
import { login } from '../auth'
import LoginPage from '../pages/LoginPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

beforeEach(async () => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(LoginPage, { onLogin: vi.fn(), oidcEnabled: false })) })
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.clearAllMocks()
})

describe('LoginPage', () => {
  it('shows a visible message when submitting empty fields', async () => {
    await act(async () => { container.querySelector('button[type="submit"]').click() })
    expect(container.textContent).toContain('Vul je gebruikersnaam en wachtwoord in.')
    expect(login).not.toHaveBeenCalled()
  })

  it('names the page in the tab title (#491)', () => {
    expect(document.title).toBe('Inloggen — openEDUdata+')
  })

  it('fills the visible height on a phone: dvh with a vh fallback (#499)', () => {
    expect(container.querySelector('main').className).toBe('login-page')
    const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')
    const regel = css.match(/\.login-page\s*\{([^}]*)\}/)[1]
    expect(regel).toMatch(/min-height:\s*100vh;\s*min-height:\s*100dvh/)
  })

  it('offers password managers the right fields', () => {
    expect(container.querySelector('#login-username').getAttribute('autocomplete')).toBe('username')
    expect(container.querySelector('#login-password').getAttribute('autocomplete')).toBe('current-password')
  })
})

describe('LoginPage notice', () => {
  const rerender = props => act(async () => { root.render(createElement(LoginPage, { onLogin: vi.fn(), oidcEnabled: false, ...props })) })
  const status = () => container.querySelector('[role="status"]')

  it('shows none after a plain logout', () => {
    expect(status()).toBeNull()
  })

  it('says the session expired when the server ended it (#499)', async () => {
    await rerender({ sessionExpired: true })
    expect(status().textContent).toBe('Je sessie is verlopen. Log opnieuw in.')
  })

  it('confirms that all data was erased and the user is logged out (#646)', async () => {
    await rerender({ gegevensVerwijderd: true })
    expect(status().textContent).toBe('Al je gegevens zijn verwijderd. Je bent uitgelogd.')
  })

  it('takes its text colour from CSS, with a readable one in dark mode', async () => {
    await rerender({ gegevensVerwijderd: true })
    expect(status().className).toBe('login-melding')
    expect(status().style.color).toBe('')
    const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')
    expect(css).toMatch(/html\.dark \.login-melding\s*\{\s*color:\s*var\(--accent-text\)/)
    expect(css).toMatch(/html:not\(\.dark\):not\(\.light\) \.login-melding\s*\{\s*color:\s*var\(--accent-text\)/)
  })
})
