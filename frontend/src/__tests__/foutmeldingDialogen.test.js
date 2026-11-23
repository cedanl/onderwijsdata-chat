// @vitest-environment jsdom
// #1131: mislukt een verzoek in een dialoog (feedback, rapportfeedback, titel opslaan, Word, opslaan op de server), dan
// staat er geen "Failed to fetch", "API 500" of "Unauthorized", maar wat er misging en wat je kunt doen; een tekst die de
// server voor gebruikers schreef blijft staan.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

const api = vi.hoisted(() => ({
  postAlgemeneFeedback: vi.fn(),
  postFeedback: vi.fn(),
  fetchFeedbackQuestions: vi.fn(),
  fetchFeedbackGiven: vi.fn(),
  putWorkbook: vi.fn(),
  updateWorkbook: vi.fn(),
}))
vi.mock('../api', async importOriginal => ({ ...(await importOriginal()), ...api }))
vi.mock('../workbooks', async importOriginal => ({ ...(await importOriginal()), updateWorkbook: api.updateWorkbook }))
vi.mock('../components/dashboards', () => ({
  InlineDashboardMijnInstelling: () => null, InlineDashboardArbeidsmarkt: () => null, InlineDashboardNationaal: () => null,
}))

import AlgemeneFeedbackModal from '../components/AlgemeneFeedbackModal'
import FeedbackModal from '../components/FeedbackModal'
import WorkbookViewer from '../components/WorkbookViewer'
import WorkbookWord from '../components/WorkbookWord'
import { syncWorkbook } from '../workbooks'
import { buildReportHtml } from '../reportHtml'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const NETWERK = () => new TypeError('Failed to fetch')
const SERVER = () => Object.assign(new Error('API 500'), { status: 500 })
const SESSIE = () => Object.assign(new Error('Unauthorized'), { status: 401 })
const TECHNISCH = /Failed to fetch|API \d|Unauthorized|\b[45]\d\d\b/

let root
let container

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

const typ = async (veld, tekst) => {
  await act(async () => {
    Object.getOwnPropertyDescriptor(veld.constructor.prototype, 'value').set.call(veld, tekst)
    veld.dispatchEvent(new Event('input', { bubbles: true }))
  })
}
const melding = () => document.querySelector('[role="alert"]').textContent

beforeEach(() => {
  for (const fn of Object.values(api)) fn.mockReset()
  api.fetchFeedbackGiven.mockResolvedValue([])
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('feedback versturen', () => {
  const stuurAlgemeen = async fout => {
    api.postAlgemeneFeedback.mockRejectedValue(fout)
    await render(createElement(AlgemeneFeedbackModal, { onClose: vi.fn() }))
    await typ(document.querySelector('textarea'), 'Een idee')
    await act(async () => { document.querySelector('form').requestSubmit() })
  }

  it.each([['een netwerkfout', NETWERK], ['een serverfout zonder tekst', SERVER], ['een verlopen sessie', SESSIE]])(
    'toont bij %s in het algemene formulier geen technische tekst', async (_naam, fout) => {
      await stuurAlgemeen(fout())
      expect(melding()).toMatch(/^Feedback niet verstuurd\. /)
      expect(melding()).not.toMatch(TECHNISCH)
      expect(document.querySelector('textarea').value).toBe('Een idee')
    })

  it('laat de tekst van de server in het algemene formulier staan', async () => {
    await stuurAlgemeen(Object.assign(new Error('Te veel feedback in korte tijd.'), { status: 429 }))
    expect(melding()).toBe('Feedback niet verstuurd: Te veel feedback in korte tijd.')
  })

  const stuurRapportfeedback = async fout => {
    api.fetchFeedbackQuestions.mockResolvedValue([{ id: 'mist', text: 'Mist er iets?', type: 'text' }])
    api.postFeedback.mockRejectedValue(fout)
    await render(createElement(FeedbackModal, { workbook: { id: 'wb-1', type: 'report', title: 'Instroom' }, onClose: vi.fn(), onSubmitted: vi.fn() }))
    await typ(document.querySelector('textarea'), 'Een opmerking')
    await act(async () => { document.querySelector('form').requestSubmit() })
  }

  it.each([['een netwerkfout', NETWERK], ['een serverfout zonder tekst', SERVER], ['een verlopen sessie', SESSIE]])(
    'toont bij %s in de rapportfeedback geen technische tekst', async (_naam, fout) => {
      await stuurRapportfeedback(fout())
      expect(melding()).toMatch(/^Feedback niet verstuurd\. /)
      expect(melding()).not.toMatch(TECHNISCH)
    })

  it('toont bij een netwerkfout geen technische tekst als de vragen niet laden', async () => {
    api.fetchFeedbackQuestions.mockRejectedValue(NETWERK())
    await render(createElement(FeedbackModal, { workbook: { id: 'wb-1', type: 'report', title: 'Instroom' }, onClose: vi.fn(), onSubmitted: vi.fn() }))
    expect(melding()).toMatch(/^Vragen niet geladen\. /)
    expect(melding()).not.toMatch(TECHNISCH)
  })
})

describe('titel opslaan', () => {
  it.each([['een netwerkfout', NETWERK], ['een serverfout zonder tekst', SERVER], ['een verlopen sessie', SESSIE]])(
    'toont bij %s geen technische tekst', async (_naam, fout) => {
      api.updateWorkbook.mockRejectedValue(fout())
      await render(createElement(WorkbookViewer, {
        workbook: { id: 'wb-1', type: 'report', title: 'Instroom hbo', htmlContent: '<p>rapport</p>' },
        onBack: vi.fn(), onUpdate: vi.fn(),
      }))
      await act(async () => { document.querySelector('.wb-viewer-title').click() })
      const invoer = document.querySelector('input.wb-viewer-title')
      await typ(invoer, 'Nieuwe titel')
      await act(async () => { invoer.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })) })
      expect(melding()).toMatch(/^Titel niet opgeslagen\. /)
      expect(melding()).not.toMatch(TECHNISCH)
    })
})

describe('Word-download', () => {
  const rapport = {
    id: 'wb-1', type: 'report', title: 'Instroom hbo',
    htmlContent: buildReportHtml({ title: 'Instroom hbo', onderzoeksvraag: 'Hoeveel?', conclusie: 'Veel.', visualisaties: [] }),
  }

  it.each([['een netwerkfout', NETWERK], ['een serverfout zonder tekst', SERVER], ['een verlopen sessie', SESSIE]])(
    'toont bij %s geen technische tekst', async (_naam, fout) => {
      const verstuur = vi.fn().mockRejectedValue(fout())
      await render(createElement(WorkbookWord, { workbook: rapport, verstuur, save: vi.fn() }))
      await act(async () => { [...container.querySelectorAll('button')].find(b => b.textContent === 'Download als Word').click() })
      expect(melding()).toMatch(/^Het Word-document kon niet worden gemaakt\. /)
      expect(melding()).not.toMatch(TECHNISCH)
    })
})

describe('opslaan op de server', () => {
  it.each([['een netwerkfout', NETWERK], ['een serverfout zonder tekst', SERVER], ['een verlopen sessie', SESSIE]])(
    'geeft bij %s een melding zonder technische tekst', async (_naam, fout) => {
      api.putWorkbook.mockRejectedValue(fout())
      const uitkomst = await syncWorkbook({ id: 'wb-1', title: 'Rapport', htmlContent: '<p>x</p>', type: 'report' })
      expect(uitkomst.ok).toBe(false)
      expect(uitkomst.error).toMatch(/^Opslaan op de server mislukt\. /)
      expect(uitkomst.error).not.toMatch(TECHNISCH)
    })

  it('houdt de statuscode apart voor wie erop beslist (413)', async () => {
    api.putWorkbook.mockRejectedValue(Object.assign(new Error('Het rapport is te groot.'), { status: 413 }))
    const uitkomst = await syncWorkbook({ id: 'wb-1', title: 'Rapport', htmlContent: '<p>x</p>', type: 'report' })
    expect(uitkomst).toMatchObject({ ok: false, status: 413, error: 'Opslaan op de server mislukt: Het rapport is te groot.' })
  })
})
