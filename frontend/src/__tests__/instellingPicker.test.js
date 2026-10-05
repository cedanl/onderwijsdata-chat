// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import InstellingPicker from '../components/InstellingPicker'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const INSTELLINGEN = [
  { naam: 'Hogeschool Utrecht', type: 'hbo', aliassen: ['HU'] },
  { naam: 'Universiteit Utrecht', type: 'wo', aliassen: ['UU'] },
  { naam: 'Universiteit Leiden', type: 'wo', aliassen: [] },
]

let root
let container

async function render(props = {}) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => INSTELLINGEN }))
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(InstellingPicker, { inputId: 'inst', value: '', onChange: vi.fn(), ...props }))
  })
}

const input = () => container.querySelector('input')
const options = () => [...container.querySelectorAll('[role="option"]')]
const emptyState = () => container.querySelector('.instelling-empty')
const niveauButton = (label) => [...container.querySelectorAll('button')].find(b => b.textContent.startsWith(label))

async function type(text) {
  await act(async () => {
    input().focus()
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    setter.call(input(), text)
    input().dispatchEvent(new Event('input', { bubbles: true }))
  })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

describe('InstellingPicker empty state', () => {
  it('explains a search without a match inside the level filter and offers to clear it', async () => {
    await render()
    await act(async () => { niveauButton('WO').click() })
    await type('Hogeschool Utrecht')
    expect(options()).toHaveLength(0)
    expect(emptyState().textContent).toContain('Geen instellingen gevonden voor ‘Hogeschool Utrecht’ binnen WO')

    await act(async () => { emptyState().querySelector('button').click() })
    expect(emptyState()).toBeNull()
    expect(options().map(o => o.textContent)).toEqual(['Hogeschool Utrechthbo'])
  })

  it('shows no filter action when no level filter is set', async () => {
    await render()
    await type('Sorbonne')
    expect(emptyState().textContent).toContain('Geen instellingen gevonden voor ‘Sorbonne’')
    expect(emptyState().querySelector('button')).toBeNull()
  })
})

describe('InstellingPicker closing', () => {
  it('closes the list when the input loses focus to the rest of the form', async () => {
    await render()
    await type('Utrecht')
    expect(options()).toHaveLength(2)
    await act(async () => { input().blur() })
    expect(options()).toHaveLength(0)
  })

  it('closes the list on selection', async () => {
    const onChange = vi.fn()
    await render({ onChange })
    await type('Leiden')
    await act(async () => { options()[0].dispatchEvent(new MouseEvent('mousedown', { bubbles: true })) })
    expect(onChange).toHaveBeenLastCalledWith('Universiteit Leiden')
    expect(options()).toHaveLength(0)
  })
})
