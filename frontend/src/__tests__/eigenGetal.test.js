// @vitest-environment jsdom
// "Wijkt af van je eigen cijfer?" (#1258): de knop alleen bij één hoofdgetal, alleen een getal als invoer, en de
// uitkomst gaat niet als historie naar het model. De regels onder een antwoord staan in de export (#1256, #1259).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import EigenGetal from '../components/EigenGetal'
import { eigenGetalFout, hoofdgetalUit, GEEN_GETAL, GROEPERING, TE_LANG } from '../eigenGetal'
import { buildHistory } from '../hooks/useChat'
import { conversationMarkdown } from '../conversationExport'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

describe('de invoer (#1258)', () => {
  it('neemt alleen een heel getal van hoogstens twaalf cijfers', () => {
    expect(eigenGetalFout('475.460')).toBeNull()
    expect(eigenGetalFout(' 475 460 ')).toBeNull()
    expect(eigenGetalFout('999999999999')).toBeNull()
    expect(eigenGetalFout('1234567890123')).toBe(TE_LANG)
    expect(eigenGetalFout('ongeveer 475.000')).toBe(GEEN_GETAL)
    expect(eigenGetalFout('475,5')).toBe(GEEN_GETAL)
    expect(eigenGetalFout('-12')).toBe(GEEN_GETAL)
    expect(eigenGetalFout('')).toBe(GEEN_GETAL)
  })

  it('neemt een punt of spatie alleen tussen groepen van drie cijfers, zoals de server', () => {
    expect(eigenGetalFout('1.234.567')).toBeNull()
    expect(eigenGetalFout('1\u00a0234\u00a0567')).toBeNull()
    for (const fout of ['1.5', '475.46', '4.7.5', '1234.567', '475.460 123']) expect(eigenGetalFout(fout), fout).toBe(GROEPERING)
    expect(eigenGetalFout('475\n460')).toBe(GEEN_GETAL)
    expect(eigenGetalFout('.')).toBe(GEEN_GETAL)
  })

  it('leest het hoofdgetal alleen zoals de server het zet', () => {
    expect(hoofdgetalUit({ hoofdgetal: { id: 'k', waarde: 475460 } })).toEqual({ id: 'k', waarde: 475460 })
    expect(hoofdgetalUit({ hoofdgetal: { id: '', waarde: 1 } })).toBeNull()
    expect(hoofdgetalUit({ hoofdgetal: { id: 'k', waarde: '1' } })).toBeNull()
    expect(hoofdgetalUit({})).toBeNull()
  })
})

describe('EigenGetal (#1258)', () => {
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
    act(() => root.render(createElement(EigenGetal, { onVerstuur: () => true, ...props })))
  }

  const typ = (veld, tekst) => {
    const zet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    act(() => {
      zet.call(veld, tekst)
      veld.dispatchEvent(new Event('input', { bubbles: true }))
    })
  }

  it('staat er niet zonder hoofdgetal', () => {
    render({ hoofdgetal: null })
    expect(container.textContent).toBe('')
  })

  it('opent een veld, weigert een niet-getal met een melding en verstuurt een getal', () => {
    const onVerstuur = vi.fn(() => true)
    render({ hoofdgetal: { id: 'k:1', waarde: 474963 }, onVerstuur })
    const knop = container.querySelector('button')
    expect(knop.textContent).toBe('Wijkt af van je eigen cijfer?')
    act(() => knop.click())

    const veld = container.querySelector('input')
    expect(veld.getAttribute('inputmode')).toBe('numeric')
    expect(container.textContent).toContain('telt nergens als bron')
    typ(veld, 'heel veel')
    act(() => container.querySelector('button[type="submit"]').click())
    expect(container.querySelector('[role="alert"]').textContent).toBe(GEEN_GETAL)
    expect(veld.getAttribute('aria-invalid')).toBe('true')
    expect(onVerstuur).not.toHaveBeenCalled()

    typ(container.querySelector('input'), '475.460')
    act(() => container.querySelector('button[type="submit"]').click())
    expect(onVerstuur).toHaveBeenCalledWith('k:1', '475.460')
    expect(container.querySelector('input')).toBeNull()
  })
})

describe('de uitkomst en de regels in historie en export', () => {
  const regels = [
    '**Andere definities:** in 2024/25 telt dit antwoord 475.460; zonder extranei 465.820 (-2,0%).',
    "**Ter controle:** DUO 'Mbo-studenten per instelling' telt in 2024/25 476.079 (alle instellingen opgeteld): 619 meer dan CBS 85354NED (475.460), +0,1%.",
  ]
  const gesprek = [
    { role: 'user', content: 'Hoeveel mbo-studenten waren er in 2024/25?' },
    { role: 'assistant', content: `In 2024/25 waren er 475.460 mbo-studenten.\n\n${regels.join('\n\n')}`, done: true, hoofdgetal: { id: 'k', waarde: 475460 } },
    { role: 'assistant', content: '**Vergelijking met je eigen cijfer:** je eigen getal 474.963 …', done: true, vast: true, verschilverklaring: true },
  ]

  it('stuurt de uitkomst bij een eigen getal niet als historie naar het model', () => {
    const history = buildHistory(gesprek, 20)
    expect(history.map(m => m.role)).toEqual(['user', 'assistant'])
    expect(history[1].content).toContain('475.460 mbo-studenten')
  })

  it('zet de regels onder het antwoord en de uitkomst in de export van het gesprek', () => {
    const md = conversationMarkdown(gesprek, { datum: '25 november 2026' })
    for (const regel of regels) expect(md).toContain(regel)
    expect(md).toContain('**Vergelijking met je eigen cijfer:** je eigen getal 474.963')
  })
})
