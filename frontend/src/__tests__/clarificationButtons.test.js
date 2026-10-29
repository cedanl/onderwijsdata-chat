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
    const onSelect = vi.fn(() => true)
    const [, tweede] = render({ onSelect, answer: { answered: false, choice: null } })
    expect(tweede.disabled).toBe(false)
    act(() => tweede.click())
    act(() => tweede.click())
    expect(onSelect).toHaveBeenCalledOnce()
    expect(onSelect).toHaveBeenCalledWith('Alle jaren')
  })

  // #774: zonder verbinding (of een andere weigering) ging er niets weg, maar de kaart zat op slot tot herladen.
  it('stays open when the choice could not be sent', () => {
    const onSelect = vi.fn(() => false)
    const [eerste, tweede] = render({ onSelect, answer: { answered: false, choice: null } })
    act(() => tweede.click())
    expect(tweede.textContent).toBe('Alle jaren — de hele reeks')
    expect(eerste.disabled).toBe(false)
    expect(tweede.disabled).toBe(false)
    act(() => tweede.click())
    expect(onSelect).toHaveBeenCalledTimes(2)
  })
})

// #494: a way back to the question when the choice went the wrong way. The choice itself stays final.
describe('ClarificationButtons: Anders formuleren (#494)', () => {
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

  it('adds nothing without a callback', () => {
    expect(render({}).map(k => k.textContent)).toEqual(['2023/24', 'Alle jaren — de hele reeks'])
  })

  it('comes after the options as a native button, named after its visible text', () => {
    const knoppen = render({ onAndersFormuleren: vi.fn() })
    const anders = knoppen.at(-1)
    expect(knoppen).toHaveLength(3)
    expect(anders.getAttribute('type')).toBe('button')
    expect(anders.textContent).toBe('Anders formuleren')
    expect(anders.getAttribute('aria-label')).toBe('Anders formuleren: zet je oorspronkelijke vraag terug in het invoerveld')
    expect(container.querySelector('.clarification-btns').contains(anders)).toBe(false)
  })

  it.each([
    ['open', { answer: { answered: false, choice: null } }, false],
    ['answered', { answer: { answered: true, choice: '2023/24' } }, true],
    ['busy', { busy: true, answer: { answered: false, choice: null } }, true],
  ])('works on a card that is %s, without choosing anything', (_, props, optiesDicht) => {
    const onSelect = vi.fn()
    const onAndersFormuleren = vi.fn()
    const knoppen = render({ ...props, onSelect, onAndersFormuleren })
    const anders = knoppen.at(-1)
    expect(anders.disabled).toBe(false)

    act(() => anders.click())

    expect(onAndersFormuleren).toHaveBeenCalledOnce()
    expect(onSelect).not.toHaveBeenCalled()
    expect(knoppen.slice(0, -1).every(k => k.disabled === optiesDicht)).toBe(true)
  })

  it('renders nothing for a message without options, also with the callback', () => {
    render({ options: null, onAndersFormuleren: vi.fn() })
    expect(container.innerHTML).toBe('')
  })
})
