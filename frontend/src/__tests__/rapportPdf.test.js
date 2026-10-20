// @vitest-environment jsdom
// #622: een rapport was alleen als HTML (4,8 MB) te downloaden. Besluit 19-10: printstijl + knop "Opslaan als PDF"
// die window.print() in het rapport aanroept; geen server-side PDF. Het frame heeft een opaque origin, dus de app
// stuurt een bericht en het rapport drukt zelf af.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { buildReportHtml, PRINT_BERICHT, PRINT_BREEDTE } from '../reportHtml'
import WorkbookPrint, { kanAfdrukken, ruimPrintframeOp, stuurAfdrukken } from '../components/WorkbookPrint'

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
    // Alleen de app mag het vragen, geen script in een ander frame (#634).
    expect(html).toContain('ev.source!==window.parent')
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
    ruimPrintframeOp()
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

  // #634: print() vraagt allow-modals, en dat geeft ook alert/confirm/prompt. Het viewerframe krijgt het niet;
  // de knop maakt een eigen printframe.
  it('drukt af in een eigen, onzichtbaar frame met allow-modals en zonder pop-ups', async () => {
    const html = buildReportHtml(spec)
    const knop = render({ html })
    expect(knop.textContent).toBe('Opslaan als PDF')
    act(() => knop.click())
    const frame = document.getElementById('edudata-printframe')
    expect(frame.getAttribute('sandbox')).toBe('allow-scripts allow-modals')
    expect(frame.getAttribute('srcdoc')).toBe(html)
    expect(frame.style.left).toBe('-10000px')
    const postMessage = vi.spyOn(frame.contentWindow, 'postMessage')
    frame.dispatchEvent(new Event('load'))
    expect(postMessage).toHaveBeenCalledWith(PRINT_BERICHT, '*')
  })

  it('houdt één printframe, ook na twee keer klikken, en ruimt het op', () => {
    const knop = render({ html: buildReportHtml(spec) })
    act(() => knop.click())
    act(() => knop.click())
    expect(document.querySelectorAll('#edudata-printframe')).toHaveLength(1)
    ruimPrintframeOp()
    expect(document.getElementById('edudata-printframe')).toBeNull()
  })

  it('ontbreekt bij een ouder rapport dat het bericht niet kent', () => {
    expect(kanAfdrukken('<html><body>oud rapport</body></html>')).toBe(false)
    expect(kanAfdrukken(null)).toBe(false)
    expect(render({ html: '<html></html>' })).toBeNull()
    expect(stuurAfdrukken(null)).toBeNull()
  })
})
