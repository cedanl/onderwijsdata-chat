// @vitest-environment jsdom
// #1038: "Download als Word" naast HTML, Markdown en PDF, alleen bij een rapport. De server maakt het document uit
// het bewaarde rapport; de knop vraagt het grafiekframe om PNG's en stuurt alleen die mee.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { buildReportHtml } from '../reportHtml'
import WorkbookWord, { ZONDER_ALLE_GRAFIEKEN } from '../components/WorkbookWord'

vi.mock('../components/dashboards', () => ({
  InlineDashboardMijnInstelling: () => null, InlineDashboardArbeidsmarkt: () => null, InlineDashboardNationaal: () => null,
}))
vi.mock('../api', async importOriginal => ({
  ...await importOriginal(),
  fetchFeedbackGiven: vi.fn().mockResolvedValue([]),
}))

import WorkbookViewer from '../components/WorkbookViewer'
import { NavSlotContext } from '../navSlot'
import { downloadRapportDocx } from '../api'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const smal = vi.hoisted(() => ({ aan: false }))
window.matchMedia = q => ({ matches: smal.aan && q === '(max-width: 1024px)', media: q, addEventListener() {}, removeEventListener() {} })

const figuur = JSON.stringify({ data: [{ type: 'bar', x: [1], y: [2] }], layout: {} })
const rapport = {
  id: 'r 1', type: 'report', title: 'Instroom hbo',
  htmlContent: buildReportHtml({
    title: 'Instroom hbo', onderzoeksvraag: 'Hoeveel?', conclusie: 'Veel.',
    visualisaties: [{ titel: 'A', figure_json: figuur }, { titel: 'B', figure_json: figuur }],
  }),
}
const PNG = 'data:image/png;base64,iVBORw0KGgo='
const docx = new Blob(['docx'])

let root
let container

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  smal.aan = false
  vi.unstubAllGlobals()
})

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => root.render(element))
  return container
}

const wordKnop = (el = container) => [...el.querySelectorAll('button')].find(b => b.textContent === 'Download als Word')
const klik = async knop => { await act(async () => { knop.click() }) }

describe('de knop "Download als Word" (#1038)', () => {
  it('staat er alleen bij een rapport', async () => {
    await render(createElement(WorkbookWord, { workbook: { id: '__builtin_nationaal__', title: 'Landelijk', builtin: true } }))
    expect(wordKnop()).toBeUndefined()
    await act(async () => root.unmount())
    await render(createElement(WorkbookWord, { workbook: { id: 'x', title: 'X', htmlContent: '<p>rapport</p>' } }))
    expect(wordKnop()).toBeUndefined()
  })

  it('vraagt de grafieken, stuurt ze mee en bewaart het document als <titel>.docx', async () => {
    const vraag = vi.fn().mockResolvedValue([PNG, PNG])
    const verstuur = vi.fn().mockResolvedValue(docx)
    const save = vi.fn()
    await render(createElement(WorkbookWord, { workbook: rapport, grafiekDoc: '<frame-doc>', vraag, verstuur, save }))
    await klik(wordKnop())
    expect(vraag).toHaveBeenCalledWith('<frame-doc>')
    const [id, form] = verstuur.mock.calls[0]
    expect(id).toBe('r 1')
    expect([...form.keys()]).toEqual(['grafiek-0', 'grafiek-1'])
    expect(save).toHaveBeenCalledWith(docx, 'Instroom_hbo.docx')
    expect(container.textContent).not.toContain(ZONDER_ALLE_GRAFIEKEN)
  })

  it('zonder rapportframe gaan er geen grafieken mee, en het zegt dat', async () => {
    const vraag = vi.fn()
    const verstuur = vi.fn().mockResolvedValue(docx)
    const save = vi.fn()
    await render(createElement(WorkbookWord, { workbook: rapport, grafiekDoc: null, vraag, verstuur, save }))
    await klik(wordKnop())
    expect(vraag).not.toHaveBeenCalled()
    expect([...verstuur.mock.calls[0][1].keys()]).toEqual([])
    expect(save).toHaveBeenCalled()
    expect(container.querySelector('[role="status"]').textContent).toBe(ZONDER_ALLE_GRAFIEKEN)
  })

  it('geeft het document ook als de grafieken mislukken of de server ze weigert', async () => {
    const save = vi.fn()
    const geweigerd = Object.assign(new Error('Een grafiek is groter dan 2 MiB.'), { status: 413 })
    const verstuur = vi.fn().mockRejectedValueOnce(geweigerd).mockResolvedValueOnce(docx)
    await render(createElement(WorkbookWord, { workbook: rapport, grafiekDoc: 'x', vraag: () => Promise.resolve([PNG]), verstuur, save }))
    await klik(wordKnop())
    expect([...verstuur.mock.calls[1][1].keys()]).toEqual([])
    expect(save).toHaveBeenCalledWith(docx, 'Instroom_hbo.docx')
    expect(container.querySelector('[role="status"]').textContent).toBe(ZONDER_ALLE_GRAFIEKEN)

    const verstuur2 = vi.fn().mockResolvedValue(docx)
    await act(async () => root.unmount())
    await render(createElement(WorkbookWord, { workbook: rapport, grafiekDoc: 'x', vraag: () => Promise.reject(new Error('x')), verstuur: verstuur2, save }))
    await klik(wordKnop())
    expect(verstuur2).toHaveBeenCalledTimes(1)
  })

  it('toont een fout als het document niet lukt', async () => {
    const save = vi.fn()
    const verstuur = vi.fn().mockRejectedValue(Object.assign(new Error('Werkboek niet gevonden'), { status: 404 }))
    await render(createElement(WorkbookWord, { workbook: rapport, verstuur, save }))
    await klik(wordKnop())
    expect(save).not.toHaveBeenCalled()
    expect(verstuur).toHaveBeenCalledTimes(1)
    expect(container.querySelector('[role="alert"]').textContent).toBe('Het Word-document kon niet worden gemaakt: Werkboek niet gevonden')
    expect(wordKnop().getAttribute('aria-disabled')).toBeNull()
  })

  it('maakt maar één document tegelijk', async () => {
    let klaar
    const verstuur = vi.fn(() => new Promise(r => { klaar = r }))
    await render(createElement(WorkbookWord, { workbook: rapport, verstuur, save: vi.fn() }))
    await klik(wordKnop())
    const bezig = [...container.querySelectorAll('button')][0]
    expect(bezig.textContent).toBe('Word-document maken…')
    expect(bezig.getAttribute('aria-disabled')).toBe('true')
    await klik(bezig)
    expect(verstuur).toHaveBeenCalledTimes(1)
    await act(async () => klaar(docx))
  })
})

describe('in de viewer', () => {
  it('staat naast Markdown in de kopbalk', async () => {
    await render(createElement(WorkbookViewer, { workbook: rapport, onBack: vi.fn(), onUpdate: vi.fn() }))
    const knoppen = [...container.querySelectorAll('.wb-viewer-actions button')].map(b => b.textContent)
    expect(knoppen.indexOf('Download als Word')).toBe(knoppen.indexOf('Download als Markdown') + 1)
  })

  it('staat op een telefoon in het ⋯-menu', async () => {
    smal.aan = true
    container = document.createElement('div')
    const slot = document.createElement('div')
    container.appendChild(slot)
    const houder = document.createElement('div')
    container.appendChild(houder)
    document.body.appendChild(container)
    root = createRoot(houder)
    await act(async () => root.render(createElement(NavSlotContext.Provider, { value: slot },
      createElement(WorkbookViewer, { workbook: rapport, onBack: vi.fn(), onUpdate: vi.fn() }))))
    await klik(slot.querySelector('button[aria-label="Meer acties"]'))
    expect(wordKnop(slot.querySelector('.navbar-meer-menu'))).not.toBeUndefined()
  })
})

describe('downloadRapportDocx', () => {
  it('post het formulier naar het rapport, met het token en zonder eigen Content-Type', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('docx', { status: 200 }))
    vi.stubGlobal('fetch', fetch)
    const form = new FormData()
    const blob = await downloadRapportDocx('r 1', form)
    expect(await blob.text()).toBe('docx')
    const [pad, opties] = fetch.mock.calls[0]
    expect(pad).toBe('/api/workbooks/r%201/docx')
    expect(opties.method).toBe('POST')
    expect(opties.body).toBe(form)
    expect(opties.headers['Content-Type']).toBeUndefined()
  })

  it('geeft de melding van de server door', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Werkboek niet gevonden' }), { status: 404 })))
    await expect(downloadRapportDocx('x', new FormData())).rejects.toMatchObject({ message: 'Werkboek niet gevonden', status: 404 })
  })
})
