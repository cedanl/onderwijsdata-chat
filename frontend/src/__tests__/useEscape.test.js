// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useEscape } from '../hooks/useEscape'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let host

function Drawer({ open, onClose }) {
  useEscape(open, onClose)
  return null
}

function render(props) {
  host = document.createElement('div')
  document.body.appendChild(host)
  root = createRoot(host)
  act(() => root.render(createElement(Drawer, props)))
}

const press = key => act(() => { document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true })) })

afterEach(() => {
  act(() => root.unmount())
  host.remove()
})

describe('useEscape (#400)', () => {
  it('sluit de open lade met Escape', () => {
    const onClose = vi.fn()
    render({ open: true, onClose })
    press('Escape')
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('reageert niet op andere toetsen of een dichte lade', () => {
    const onClose = vi.fn()
    render({ open: false, onClose })
    press('Escape')
    act(() => root.render(createElement(Drawer, { open: true, onClose })))
    press('Enter')
    expect(onClose).not.toHaveBeenCalled()
  })
})
