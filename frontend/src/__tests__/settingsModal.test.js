// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import SettingsModal, { GEAVANCEERD_VRAAG } from '../components/SettingsModal'

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

describe('SettingsModal: Exporteer al mijn gegevens alleen met een eigen account (#1118)', () => {
  const exportButton = () => container.querySelector('.mijn-gegevens-export-btn')

  it('offers it with a login of one\'s own, the same condition as Verwijder al mijn gegevens', async () => {
    await render({ onLogout: vi.fn(), onGegevensVerwijderd: vi.fn() })
    expect(exportButton().textContent).toBe('Exporteer al mijn gegevens')
  })

  it('does not offer it without one: the export of the shared guest would hold the work of every visitor', async () => {
    await render({ onLogout: null, onGegevensVerwijderd: null })
    expect(exportButton()).toBeNull()
    expect(container.textContent).not.toContain('Exporteer al mijn gegevens')
  })
})

describe('SettingsModal tap targets', () => {
  it('carries the class the 44px touch rule for its buttons hangs on (#490)', async () => {
    await render({})
    expect(container.querySelector('[role="dialog"]').classList.contains('settings-modal')).toBe(true)
  })
})

describe('SettingsModal weergave (#779)', () => {
  const button = text => [...container.querySelectorAll('button')].find(b => b.textContent === text)

  it('zegt met aria-pressed welk thema gekozen is, zoals bij de functies', async () => {
    await render({ settings: { mode: 'dark' } })
    expect(button('Donker').getAttribute('aria-pressed')).toBe('true')
    expect(button('Licht').getAttribute('aria-pressed')).toBe('false')
    expect(button('Systeem').getAttribute('aria-pressed')).toBe('false')

    await act(async () => { button('Licht').click() })
    expect(button('Licht').getAttribute('aria-pressed')).toBe('true')
    expect(button('Donker').getAttribute('aria-pressed')).toBe('false')
  })
})

describe('SettingsModal: Geavanceerd (#1269)', () => {
  const schakelaar = () => container.querySelector('[role="switch"]')
  const button = text => [...container.querySelectorAll('button')].find(b => b.textContent === text)

  it('has a switch named Geavanceerd, off by default', async () => {
    await render({})
    expect(schakelaar().textContent).toBe('Geavanceerd')
    expect(schakelaar().getAttribute('aria-checked')).toBe('false')
    // The explanation says what it adds, and that the checks stay.
    const uitleg = document.getElementById(schakelaar().getAttribute('aria-describedby')).textContent
    expect(uitleg).toContain('code')
    expect(uitleg).toContain('altijd')
  })

  it('saves the choice as geavanceerd, next to the profile', async () => {
    const onSave = vi.fn()
    await render({ onSave })
    await act(async () => { schakelaar().click() })
    expect(schakelaar().getAttribute('aria-checked')).toBe('true')
    await act(async () => { button('Opslaan').click() })
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ geavanceerd: true }))
  })

  it('starts on the stored value and can switch it off', async () => {
    const onSave = vi.fn()
    await render({ onSave, geavanceerd: true })
    expect(schakelaar().getAttribute('aria-checked')).toBe('true')
    await act(async () => { schakelaar().click() })
    await act(async () => { button('Opslaan').click() })
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ geavanceerd: false }))
  })

  it('is no profile field: a stored geavanceerd in the settings does not switch it on', async () => {
    await render({ settings: { geavanceerd: true, functie: 'IR-specialist' } })
    expect(schakelaar().getAttribute('aria-checked')).toBe('false')
  })
})

describe('SettingsModal: the onboarding question about the work (#1269)', () => {
  const button = text => [...container.querySelectorAll('button')].find(b => b.textContent === text)
  const vraag = () => [...container.querySelectorAll('[role="group"]')]
    .find(g => document.getElementById(g.getAttribute('aria-labelledby'))?.textContent === GEAVANCEERD_VRAAG)

  it('asks whether to see the code and data behind an answer, with Nee chosen', async () => {
    await render({ isOnboarding: true })
    expect(GEAVANCEERD_VRAAG).toBe('Wil je de code en de data achter een antwoord zien en zelf bijsturen?')
    expect(vraag()).toBeDefined()
    expect(button('Nee').getAttribute('aria-pressed')).toBe('true')
    expect(button('Ja').getAttribute('aria-pressed')).toBe('false')
    // During onboarding the question takes the place of the switch.
    expect(container.querySelector('[role="switch"]')).toBeNull()
  })

  it('saves Nee as off when the user does not answer', async () => {
    const onSave = vi.fn()
    await render({ isOnboarding: true, onSave })
    await act(async () => { button('Opslaan').click() })
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ geavanceerd: false }))
  })

  it('saves Ja as on', async () => {
    const onSave = vi.fn()
    await render({ isOnboarding: true, onSave })
    await act(async () => { button('Ja').click() })
    expect(button('Ja').getAttribute('aria-pressed')).toBe('true')
    expect(button('Nee').getAttribute('aria-pressed')).toBe('false')
    await act(async () => { button('Opslaan').click() })
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ geavanceerd: true }))
  })
})
