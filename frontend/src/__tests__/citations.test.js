// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ReactMarkdown from 'react-markdown'
import CitedNumber from '../components/CitedNumber'
import { rehypeCitaties } from '../citations'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const CITATIES = [{
  getal: '378.490', vastgesteld: true, stap: 3, tool: 'query_data', label: 'Data gefilterd',
  bron: 'CBS · Studenten; onderwijssoort', maat: 'Totaal', eenheid: 'aantal',
  selectie: 'Onderwijssoort: Hbo · Perioden: 2024', data_key: 'cbs:85353NED:854e2215',
}]

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
    expect(uitleg.textContent).toContain('Data gefilterd')
    expect(knop.getAttribute('aria-expanded')).toBe('true')
    act(() => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })) })
    expect(container.querySelector('[role="note"]')).toBeNull()
  })

  it('zet bron en filters in woorden bovenaan, de hash eronder (#415)', () => {
    toon('Er waren 378.490 studenten.')
    act(() => container.querySelector('button').click())
    const regels = [...container.querySelector('[role="note"]').children].map(r => r.textContent)
    expect(regels[0]).toBe('CBS · Studenten; onderwijssoort')
    expect(regels[1]).toBe('Onderwijssoort: Hbo · Perioden: 2024')
    expect(regels).toContain('Totaal (aantal)')
    expect(regels.at(-1)).toBe('cbs:85353NED:854e2215')
  })

  it('zegt het als de herkomst niet is vastgesteld (#415)', () => {
    toon('Er waren 36.201 studenten.', [{ getal: '36.201', vastgesteld: false }])
    act(() => container.querySelector('button').click())
    const uitleg = container.querySelector('[role="note"]')
    expect(uitleg.textContent).toContain('Herkomst niet vastgesteld')
    expect(container.querySelector('.citatie-getal').classList.contains('citatie-onbepaald')).toBe(true)
  })

  it('zegt dat een getal zonder meetwaarde niet in de data staat', () => {
    toon('Er waren 36.201 studenten.', [{ getal: '36.201', vastgesteld: false, reden: 'geen_meetwaarde' }])
    act(() => container.querySelector('button').click())
    expect(container.querySelector('[role="note"]').textContent).toContain('staat niet als meetwaarde in de opgehaalde data')
  })

  // CH-38 (#458): een getal dat meer dan eens in de data staat, staat er wél in.
  it('zegt bij twijfel tussen plekken dat het getal er meer dan eens in staat', () => {
    toon('Er waren 36.201 studenten.', [{ getal: '36.201', vastgesteld: false, reden: 'meerdere' }])
    act(() => container.querySelector('button').click())
    const uitleg = container.querySelector('[role="note"]').textContent
    expect(uitleg).toContain('meer dan eens in de opgehaalde data')
    expect(uitleg).not.toContain('staat niet als meetwaarde')
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
