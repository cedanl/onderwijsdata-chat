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

// Every element that gets focus while fn runs, including focus that moves on again before fn ends.
// Focus does not bubble, so listen in the capture phase.
async function focusedDuring(fn) {
  const focused = []
  const record = e => focused.push(e.target)
  document.addEventListener('focus', record, true)
  try {
    await fn()
  } finally {
    document.removeEventListener('focus', record, true)
  }
  return focused
}

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

describe('stacked dialogs (#572)', () => {
  let upperHost
  let upperRoot
  let onUpperCancel

  beforeEach(async () => {
    upperHost = document.createElement('div')
    document.body.appendChild(upperHost)
    upperRoot = createRoot(upperHost)
    onUpperCancel = vi.fn()
    host.querySelector('button').focus()
    await act(async () => {
      upperRoot.render(createElement(ConfirmModal, { message: 'Bovenste?', onConfirm: vi.fn(), onCancel: onUpperCancel }))
    })
  })

  afterEach(() => {
    act(() => upperRoot.unmount())
    upperHost.remove()
  })

  it('Escape closes only the topmost dialog', async () => {
    await press('Escape')
    expect(onUpperCancel).toHaveBeenCalledOnce()
    expect(onCancel).not.toHaveBeenCalled()
  })

  it('Tab stays in the topmost dialog', async () => {
    const [first, last] = [...upperHost.querySelectorAll('button')]
    last.focus()
    const focused = await focusedDuring(() => press('Tab'))
    expect(focused.filter(el => host.contains(el)), 'focus in the lower dialog').toEqual([])
    expect(document.activeElement).toBe(first)
  })

  it('the lower dialog handles keys again once the upper one is gone', async () => {
    const lowerButton = host.querySelector('button')
    act(() => upperRoot.unmount())
    expect(document.activeElement).toBe(lowerButton)
    upperRoot = createRoot(upperHost)
    await press('Escape')
    expect(onCancel).toHaveBeenCalledOnce()
    expect(onUpperCancel).not.toHaveBeenCalled()
  })
})
