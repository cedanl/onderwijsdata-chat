// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
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

  it('offers password managers the right fields', () => {
    expect(container.querySelector('#login-username').getAttribute('autocomplete')).toBe('username')
    expect(container.querySelector('#login-password').getAttribute('autocomplete')).toBe('current-password')
  })
})
