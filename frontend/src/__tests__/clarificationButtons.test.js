// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ClarificationButtons from '../components/ClarificationButtons'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const OPTIES = ['2023/24', { label: 'Alle jaren', beschrijving: 'de hele reeks' }]

describe('ClarificationButtons (#109)', () => {
  let root
  let container

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  function render(props) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    act(() => root.render(createElement(ClarificationButtons, { options: OPTIES, onSelect: () => {}, busy: false, ...props })))
    return [...container.querySelectorAll('button')]
  }

  it('keeps the chosen option marked and the card closed after a reload', () => {
    const [eerste, tweede] = render({ answer: { answered: true, choice: '2023/24' } })
    expect(eerste.textContent).toBe('✓ 2023/24')
    expect(eerste.className).toContain('selected')
    expect(eerste.disabled).toBe(true)
    expect(tweede.disabled).toBe(true)
  })

  it('closes the card when a question was typed instead', () => {
    const knoppen = render({ answer: { answered: true, choice: 'toon hbo' } })
    expect(knoppen.every(k => k.disabled)).toBe(true)
    expect(knoppen.some(k => k.className.includes('selected'))).toBe(false)
  })

  it('an open card can be answered once', () => {
    const onSelect = vi.fn()
    const [, tweede] = render({ onSelect, answer: { answered: false, choice: null } })
    expect(tweede.disabled).toBe(false)
    act(() => tweede.click())
    act(() => tweede.click())
    expect(onSelect).toHaveBeenCalledOnce()
    expect(onSelect).toHaveBeenCalledWith('Alle jaren')
  })
})
