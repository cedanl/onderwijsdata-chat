// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import SettingsModal from '../components/SettingsModal'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function render(props) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(SettingsModal, { settings: {}, onSave: vi.fn(), onClose: vi.fn(), ...props }))
  })
}

const logoutButton = () => [...container.querySelectorAll('button')].find(b => b.textContent === 'Uitloggen')

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('SettingsModal logout', () => {
  it('offers Uitloggen, which the navbar hides on phones and tablets', async () => {
    const onLogout = vi.fn()
    await render({ onLogout })
    await act(async () => { logoutButton().click() })
    expect(onLogout).toHaveBeenCalledOnce()
  })

  it('does not offer it during onboarding', async () => {
    await render({ onLogout: vi.fn(), isOnboarding: true })
    expect(logoutButton()).toBeUndefined()
  })

  it('does not offer it when login is not required', async () => {
    await render({ onLogout: null })
    expect(logoutButton()).toBeUndefined()
  })
})
