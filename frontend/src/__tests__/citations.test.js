// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ReactMarkdown from 'react-markdown'
import CitedNumber from '../components/CitedNumber'
import { rehypeCitaties } from '../citations'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const CITATIES = [{ getal: '378.490', tool: 'get_cbs_data', label: 'CBS-data ophalen', bron: 'CBS 85423NED', data_key: 'cbs:1' }]

describe('zichtbare citaties (#365)', () => {
  let root
  let container

  function toon(tekst, citaties = CITATIES) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    act(() => root.render(
      createElement(ReactMarkdown, { rehypePlugins: [rehypeCitaties(citaties)], components: { span: CitedNumber } }, tekst)
    ))
  }

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it('maakt alleen het gecontroleerde getal een knop', () => {
    toon('Er waren 378.490 studenten, 12.345 vorig jaar.')
    const knoppen = container.querySelectorAll('button')
    expect(knoppen).toHaveLength(1)
    expect(knoppen[0].textContent).toBe('378.490')
  })

  it('toont de herkomst na een klik en sluit met Escape', () => {
    toon('Er waren 378.490 studenten.')
    const knop = container.querySelector('button')
    expect(knop.getAttribute('aria-expanded')).toBe('false')
    act(() => knop.click())
    const uitleg = container.querySelector('[role="note"]')
    expect(uitleg.textContent).toContain('CBS-data ophalen')
    expect(uitleg.textContent).toContain('CBS 85423NED')
    expect(knop.getAttribute('aria-expanded')).toBe('true')
    act(() => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })) })
    expect(container.querySelector('[role="note"]')).toBeNull()
  })

  it('laat getallen in code en onderdelen van een groter getal met rust', () => {
    toon('Code `378.490` en 1378.490 en 378.490,5.')
    expect(container.querySelectorAll('button')).toHaveLength(0)
  })

  it('doet niets zonder citaties', () => {
    toon('Er waren 378.490 studenten.', [])
    expect(container.querySelectorAll('button')).toHaveLength(0)
  })
})
