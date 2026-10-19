// @vitest-environment jsdom
// #622: een rapport was alleen als HTML (4,8 MB) te downloaden. Besluit 19-10: printstijl + knop "Opslaan als PDF"
// die window.print() in het rapport aanroept; geen server-side PDF. Het frame heeft een opaque origin, dus de app
// stuurt een bericht en het rapport drukt zelf af.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { buildReportHtml, PRINT_BERICHT, PRINT_BREEDTE } from '../reportHtml'
import WorkbookPrint, { kanAfdrukken, stuurAfdrukken } from '../components/WorkbookPrint'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const spec = {
  title: 'Instroom', onderzoeksvraag: 'Hoe?', auteur: 'jansen', datum: '19 oktober 2026',
  visualisaties: [{ titel: 'Grafiek', figure_json: JSON.stringify({ data: [{ type: 'bar', x: [1], y: [2] }], layout: {} }) }],
  conclusie: 'Zo.',
}

describe('het rapport kan zichzelf afdrukken', () => {
  const html = buildReportHtml(spec)

  it('heeft een printstijl voor A4 met licht thema, kaarten en grafieken op één pagina', () => {
    expect(html).toContain('@media print{')
    expect(html).toContain('@page{size:A4;margin:14mm}')
    expect(html).toContain('background:#fff!important')
    expect(html).toMatch(/\.vis{break-inside:avoid/)
  })

  it('drukt af op het bericht van de app: eerst licht thema en grafieken op A4-breedte, daarna alles terug', () => {
    expect(html).toContain(`ev.data!=='${PRINT_BERICHT}'`)
    expect(html).toContain('window.print()')
    expect(html).toContain(`B.style.width='${PRINT_BREEDTE}px'`)
    expect(html).toContain("H.classList.remove('dark');H.classList.add('light')")
    expect(html).toContain("addEventListener('afterprint',herstellen)")
  })
})

describe('de knop "Opslaan als PDF"', () => {
  let root
  let container

  afterEach(() => {
    if (root) act(() => root.unmount())
    container?.remove()
    root = null
  })

  function render(props) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    act(() => root.render(createElement(WorkbookPrint, props)))
    return container.querySelector('button')
  }

  it('stuurt het printbericht naar het rapportframe', () => {
    const postMessage = vi.fn()
    const frameRef = { current: { contentWindow: { postMessage } } }
    const knop = render({ frameRef, html: buildReportHtml(spec) })
    expect(knop.textContent).toBe('Opslaan als PDF')
    act(() => knop.click())
    expect(postMessage).toHaveBeenCalledWith(PRINT_BERICHT, '*')
  })

  it('ontbreekt bij een ouder rapport dat het bericht niet kent', () => {
    expect(kanAfdrukken('<html><body>oud rapport</body></html>')).toBe(false)
    expect(kanAfdrukken(null)).toBe(false)
    expect(render({ frameRef: { current: null }, html: '<html></html>' })).toBeNull()
    expect(() => stuurAfdrukken(null)).not.toThrow()
  })
})
