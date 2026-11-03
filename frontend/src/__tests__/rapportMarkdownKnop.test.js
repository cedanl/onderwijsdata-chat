// @vitest-environment jsdom
// #746: de knop "Download als Markdown" naast "Download als HTML" en "Opslaan als PDF", alleen bij een rapport.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { buildReportHtml } from '../reportHtml'
import WorkbookMarkdown from '../components/WorkbookMarkdown'

vi.mock('../components/dashboards', () => ({
  InlineDashboardMijnInstelling: () => null, InlineDashboardArbeidsmarkt: () => null, InlineDashboardNationaal: () => null,
}))

import WorkbookViewer from '../components/WorkbookViewer'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const rapport = {
  id: 'r', type: 'report', title: 'Instroom hbo',
  htmlContent: buildReportHtml({ title: 'Instroom hbo', datum: '30 oktober 2026', onderzoeksvraag: 'Hoeveel?', conclusie: 'Veel.' }),
}

let root
let container

afterEach(() => {
  if (root) act(() => root.unmount())
  container?.remove()
  root = null
})

function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root.render(element))
  return container
}

const markdownKnop = () => [...container.querySelectorAll('button')].find(b => b.textContent === 'Download als Markdown')

describe('de knop "Download als Markdown" (#746)', () => {
  it('downloadt het rapport als .md-bestand', async () => {
    const save = vi.fn()
    render(createElement(WorkbookMarkdown, { workbook: rapport, save }))
    const knop = markdownKnop()
    expect(knop.getAttribute('type')).toBe('button')
    act(() => knop.click())
    const [blob, naam] = save.mock.calls[0]
    expect(naam).toBe('Instroom_hbo.md')
    expect(blob.type).toBe('text/markdown;charset=utf-8')
    expect(await blob.text()).toContain('# Instroom hbo\n\nGegenereerd op 30 oktober 2026')
  })

  it('staat er niet bij een dashboard of bij HTML die geen rapport is', () => {
    render(createElement(WorkbookMarkdown, { workbook: { id: '__builtin_nationaal__', title: 'Landelijk', builtin: true } }))
    expect(markdownKnop()).toBeUndefined()
    act(() => root.unmount())
    root = null
    container.remove()
    render(createElement(WorkbookMarkdown, { workbook: { id: 'x', title: 'X', htmlContent: '<p>rapport</p>' } }))
    expect(markdownKnop()).toBeUndefined()
  })

  it('staat in de viewer naast de HTML-download', () => {
    render(createElement(WorkbookViewer, { workbook: rapport, onBack: vi.fn(), onUpdate: vi.fn() }))
    const knoppen = [...container.querySelectorAll('.wb-viewer-actions button')].map(b => b.textContent)
    expect(knoppen.indexOf('Download als Markdown')).toBe(knoppen.indexOf('Download als HTML') + 1)
  })
})
