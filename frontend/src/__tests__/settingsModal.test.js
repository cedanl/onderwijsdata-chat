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

describe('SettingsModal functie (#591)', () => {
  const button = text => [...container.querySelectorAll('button')].find(b => b.textContent === text)

  it('offers Docent; choosing it and saving passes it on', async () => {
    const onSave = vi.fn()
    await render({ onSave })
    expect(button('Docent').getAttribute('aria-pressed')).toBe('false')

    await act(async () => { button('Docent').click() })
    expect(button('Docent').getAttribute('aria-pressed')).toBe('true')
    await act(async () => { button('Opslaan').click() })

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ functie: 'Docent' }))
  })

  it('deselects a role on a second click', async () => {
    const onSave = vi.fn()
    await render({ onSave, settings: { functie: 'Docent' } })
    expect(button('Docent').getAttribute('aria-pressed')).toBe('true')

    await act(async () => { button('Docent').click() })
    await act(async () => { button('Opslaan').click() })

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ functie: '' }))
  })
})

describe('SettingsModal: Verwijder al mijn gegevens (#646)', () => {
  const deleteButton = () => container.querySelector('.mijn-gegevens-verwijderen-btn')

  it('offers it with a callback, under the export and before Uitloggen', async () => {
    await render({ onLogout: vi.fn(), onGegevensVerwijderd: vi.fn() })
    expect(deleteButton().textContent).toBe('Verwijder al mijn gegevens')
    const section = deleteButton().parentElement
    expect(section.previousElementSibling.querySelector('.mijn-gegevens-export-btn')).not.toBeNull()
    expect(section.nextElementSibling).toBe(logoutButton())
  })

  it('does not offer it without a callback (login off: everyone is the shared guest)', async () => {
    await render({ onLogout: null, onGegevensVerwijderd: null })
    expect(deleteButton()).toBeNull()
    expect(container.textContent).not.toContain('Verwijder al mijn gegevens')
  })

  it('does not offer it during onboarding', async () => {
    await render({ onLogout: vi.fn(), onGegevensVerwijderd: vi.fn(), isOnboarding: true })
    expect(deleteButton()).toBeNull()
  })
})

describe('SettingsModal tap targets', () => {
  it('carries the class the 44px touch rule for its buttons hangs on (#490)', async () => {
    await render({})
    expect(container.querySelector('[role="dialog"]').classList.contains('settings-modal')).toBe(true)
  })
})
