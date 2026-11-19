// @vitest-environment jsdom
// De exportformaten van een geopend rapport op desktop staan achter één knop "Downloaden" in plaats van vier
// knoppen naast elkaar (HTML, Markdown, Word, PDF). Het paneel volgt het disclosure-patroon: de knop zegt met
// aria-expanded of het open is, Escape en een klik ernaast sluiten het. Het blijft gemount (hidden), zodat een lopende
// Word-download en haar melding niet verdwijnen als iemand het paneel sluit.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { buildReportHtml } from '../reportHtml'
import RapportExportMenu from '../components/RapportExportMenu'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const rapport = {
  id: 'r', type: 'report', title: 'Instroom hbo',
  htmlContent: buildReportHtml({ title: 'Instroom hbo', datum: '30 oktober 2026', onderzoeksvraag: 'Hoeveel?', conclusie: 'Veel.' }),
}

let root
let container

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = null
})

function render(props) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root.render(createElement(RapportExportMenu, { workbook: rapport, save: vi.fn(), ...props })))
  return container
}

const knop = () => container.querySelector('button[aria-haspopup="true"]')
const paneel = () => container.querySelector(`#${knop().getAttribute('aria-controls')}`)
const formaten = () => [...paneel().querySelectorAll('button')].map(b => b.textContent)

describe('exportmenu van een rapport', () => {
  it('toont één knop Downloaden, dicht', () => {
    render()
    expect(knop().textContent).toContain('Downloaden')
    expect(knop().getAttribute('aria-expanded')).toBe('false')
    expect(paneel().hidden).toBe(true)
  })

  it('opent met de formaten, in vaste volgorde', () => {
    render()
    act(() => knop().click())
    expect(knop().getAttribute('aria-expanded')).toBe('true')
    expect(paneel().hidden).toBe(false)
    expect(formaten()).toEqual(['Download als HTML', 'Download als Markdown', 'Download als Word'])
  })

  it('noemt PDF als laatste als het rapport kan afdrukken', () => {
    // printDoc is wat useReportFrame het printframe geeft; een rapport van buildReportHtml kent het printbericht.
    render({ printDoc: rapport.htmlContent })
    act(() => knop().click())
    expect(formaten()).toEqual(['Download als HTML', 'Download als Markdown', 'Download als Word', 'Opslaan als PDF'])
  })

  it('verschijnt ook met alleen PDF, en zonder printDoc zonder PDF', () => {
    render({ workbook: { id: 'b', title: 'B', builtin: true }, printDoc: rapport.htmlContent })
    act(() => knop().click())
    expect(formaten()).toEqual(['Opslaan als PDF'])
  })

  it('blijft open na een keuze, zodat een melding zichtbaar blijft', async () => {
    const save = vi.fn()
    render({ save })
    act(() => knop().click())
    await act(async () => paneel().querySelector('button').click())
    expect(save).toHaveBeenCalledOnce()
    expect(paneel().hidden).toBe(false)
  })

  it('sluit met Escape en geeft de focus terug aan de knop', () => {
    render()
    act(() => knop().click())
    act(() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })))
    expect(paneel().hidden).toBe(true)
    expect(document.activeElement).toBe(knop())
  })

  it('sluit bij een klik ernaast, niet bij een klik erin', () => {
    render()
    act(() => knop().click())
    act(() => paneel().dispatchEvent(new MouseEvent('mousedown', { bubbles: true })))
    expect(paneel().hidden).toBe(false)
    act(() => document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })))
    expect(paneel().hidden).toBe(true)
  })

  it('verschijnt niet als er niets te downloaden is (een ingebouwd dashboard)', () => {
    render({ workbook: { id: '__builtin_nationaal__', title: 'Landelijk', builtin: true } })
    expect(container.innerHTML).toBe('')
  })
})
