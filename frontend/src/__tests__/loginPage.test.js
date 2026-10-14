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
