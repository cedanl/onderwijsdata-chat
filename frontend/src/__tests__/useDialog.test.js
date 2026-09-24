// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ConfirmModal from '../components/ConfirmModal'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let host
let opener
let onCancel

const press = (key, opts = {}) =>
  act(async () => { document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...opts })) })
const buttons = () => [...host.querySelectorAll('button')]

beforeEach(async () => {
  opener = document.createElement('button')
  document.body.appendChild(opener)
  opener.focus()
  host = document.createElement('div')
  document.body.appendChild(host)
  root = createRoot(host)
  onCancel = vi.fn()
  await act(async () => {
    root.render(createElement(ConfirmModal, { message: 'Gesprek verwijderen?', onConfirm: vi.fn(), onCancel }))
  })
})

afterEach(() => {
  act(() => root.unmount())
  host.remove()
  opener.remove()
})

describe('dialog focus', () => {
  it('is announced as a dialog with its question', () => {
    const dialog = host.querySelector('[role="alertdialog"]')
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(document.getElementById(dialog.getAttribute('aria-describedby')).textContent).toBe('Gesprek verwijderen?')
  })

  it('moves focus into the dialog, to the safe choice', () => {
    expect(document.activeElement.textContent).toBe('Annuleren')
  })

  it('keeps Tab inside the dialog in both directions', async () => {
    const [first, last] = buttons()
    last.focus()
    await press('Tab')
    expect(document.activeElement).toBe(first)
    await press('Tab', { shiftKey: true })
    expect(document.activeElement).toBe(last)
  })

  it('closes on Escape', async () => {
    await press('Escape')
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('gives focus back to what opened it', () => {
    act(() => root.unmount())
    expect(document.activeElement).toBe(opener)
    root = createRoot(host)
  })
})
