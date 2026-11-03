// @vitest-environment jsdom
// #908: bij "Genereer rapport" vraagt de app de server om de beurten met data (report_checklist) en stuurt de gekozen
// beurten mee in het rapportverzoek. Hier de verbinding (useChat) en de kleine helpers; de dialoog zelf staat in
// rapportChecklistDialoog.test.js.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useChat, CHECKLIST_TIMEOUT_MS } from '../hooks/useChat'
import { metKeuze, aanBeurten, voortbouwNotitie } from '../rapportKeuze'
import { FakeWebSocket } from './fakeWebSocket'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const ITEMS = [
  { beurt: 1, vraag: 'Hoeveel studenten heeft de UU?', bronnen: ['DUO — Ingeschrevenen (p01hoinges)'], bouwt_voort_op: [] },
  { beurt: 2, vraag: 'Even wat anders: het wo-rendement', bronnen: ['CBS — Rendement (83285NED)'], bouwt_voort_op: [] },
  { beurt: 3, vraag: 'Alleen de vrouwen', bronnen: ['DUO — Ingeschrevenen (p01hoinges)'], bouwt_voort_op: [1] },
]

let root
let chat

async function mount({ open = true } = {}) {
  function Harness() {
    chat = useChat()
    return null
  }
  root = createRoot(document.createElement('div'))
  await act(async () => { root.render(createElement(Harness)) })
  if (open) await act(async () => { FakeWebSocket.last.open() })
  return FakeWebSocket.last
}

const checklistFrames = ws => ws.sent.filter(m => m.action === 'report_checklist')

beforeEach(() => {
  FakeWebSocket.reset()
  globalThis.WebSocket = FakeWebSocket
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
})

afterEach(() => {
  if (root) act(() => root.unmount())
  root = null
  vi.useRealTimers()
})

describe('de checklist ophalen (#908)', () => {
  it('is er niet voordat erom gevraagd is', async () => {
    await mount()
    expect(chat.reportChecklist).toBeNull()
  })

  it('vraagt de server erom en wacht op het antwoord', async () => {
    const ws = await mount()

    await act(async () => { chat.requestReportChecklist() })

    expect(checklistFrames(ws)).toHaveLength(1)
    expect(chat.reportChecklist).toEqual({ status: 'laden', items: [] })
  })

  it('toont de beurten zodra het frame binnen is', async () => {
    const ws = await mount()
    await act(async () => { chat.requestReportChecklist() })

    await act(async () => { ws.emit({ type: 'report_checklist', items: ITEMS }) })

    expect(chat.reportChecklist).toEqual({ status: 'klaar', items: ITEMS })
  })

  it('een leeg antwoord is klaar zonder beurten: de dialoog is dan alleen het veld', async () => {
    const ws = await mount()
    await act(async () => { chat.requestReportChecklist() })

    await act(async () => { ws.emit({ type: 'report_checklist', items: [] }) })

    expect(chat.reportChecklist).toEqual({ status: 'klaar', items: [] })
  })

  it('een misvormd antwoord is een fout, geen lijst om op te vertrouwen', async () => {
    const ws = await mount()
    await act(async () => { chat.requestReportChecklist() })

    await act(async () => { ws.emit({ type: 'report_checklist', items: 'geen lijst' }) })

    expect(chat.reportChecklist.status).toBe('fout')
  })

  it('beurten zonder nummer of vraag worden niet doorgegeven', async () => {
    const ws = await mount()
    await act(async () => { chat.requestReportChecklist() })

    await act(async () => { ws.emit({ type: 'report_checklist', items: [ITEMS[0], { vraag: 'zonder nummer' }, null, { beurt: 'x', vraag: 'y' }] }) })

    expect(chat.reportChecklist).toEqual({ status: 'klaar', items: [ITEMS[0]] })
  })

  it('een frame zonder dat erom gevraagd is verandert niets', async () => {
    const ws = await mount()

    await act(async () => { ws.emit({ type: 'report_checklist', items: ITEMS }) })

    expect(chat.reportChecklist).toBeNull()
  })

  it('zonder antwoord wordt het na een paar seconden een fout, en gaat het rapport door met het hele gesprek', async () => {
    await mount()
    await act(async () => { chat.requestReportChecklist() })

    await act(async () => { vi.advanceTimersByTime(CHECKLIST_TIMEOUT_MS) })

    expect(chat.reportChecklist).toEqual({ status: 'fout', items: [] })
  })

  it('zonder verbinding is het meteen een fout en gaat er niets de deur uit', async () => {
    const ws = await mount({ open: false })

    await act(async () => { chat.requestReportChecklist() })

    expect(chat.reportChecklist.status).toBe('fout')
    expect(checklistFrames(ws)).toHaveLength(0)
  })

  it('een nieuw gesprek begint zonder checklist', async () => {
    const ws = await mount()
    await act(async () => { chat.requestReportChecklist() })
    await act(async () => { ws.emit({ type: 'report_checklist', items: ITEMS }) })

    await act(async () => { chat.startNewConversation() })

    expect(chat.reportChecklist).toBeNull()
  })

  it('opnieuw vragen begint opnieuw bij laden, niet bij de oude lijst', async () => {
    const ws = await mount()
    await act(async () => { chat.requestReportChecklist() })
    await act(async () => { ws.emit({ type: 'report_checklist', items: ITEMS }) })

    await act(async () => { chat.requestReportChecklist() })

    expect(chat.reportChecklist).toEqual({ status: 'laden', items: [] })
    expect(checklistFrames(ws)).toHaveLength(2)
  })
})

describe('de gekozen beurten meesturen (#908)', () => {
  const rapportFrame = ws => ws.sent.find(m => m.action === 'generate_report')

  it('gaan mee naast de onderzoeksvraag', async () => {
    const ws = await mount()

    await act(async () => { chat.generateReport('tester', 'Mijn vraag', [1, 3]) })

    expect(rapportFrame(ws)).toEqual({ action: 'generate_report', author: 'tester', onderzoeksvraag: 'Mijn vraag', beurten: [1, 3] })
  })

  it('zonder keuze gaat er niets extra mee: het frame is dat van voor de checklist', async () => {
    const ws = await mount()

    await act(async () => { chat.generateReport('tester', 'Mijn vraag') })

    expect(rapportFrame(ws)).toEqual({ action: 'generate_report', author: 'tester', onderzoeksvraag: 'Mijn vraag' })
  })
})

describe('de helpers (#908)', () => {
  it('een checklist is er pas met een keuze te maken: klaar en minstens twee beurten', () => {
    expect(metKeuze({ status: 'klaar', items: ITEMS })).toBe(true)
    expect(metKeuze({ status: 'klaar', items: [ITEMS[0]] })).toBe(false)
    expect(metKeuze({ status: 'klaar', items: [] })).toBe(false)
    expect(metKeuze({ status: 'laden', items: [] })).toBe(false)
    expect(metKeuze({ status: 'fout', items: [] })).toBe(false)
    expect(metKeuze(null)).toBe(false)
  })

  it('alles staat aan tot de gebruiker iets uitzet', () => {
    expect(aanBeurten(ITEMS, new Set())).toEqual([1, 2, 3])
    expect(aanBeurten(ITEMS, new Set([2]))).toEqual([1, 3])
    expect(aanBeurten(ITEMS, new Set([1, 2, 3]))).toEqual([])
  })

  it('zegt waar een beurt op voortbouwt, en dat die bron vermeld blijft', () => {
    expect(voortbouwNotitie(ITEMS[0], ITEMS)).toBeNull()
    expect(voortbouwNotitie(ITEMS[2], ITEMS)).toBe('Bouwt voort op “Hoeveel studenten heeft de UU?”. Die bron blijft vermeld.')
  })

  it('kort een lange vraag in de notitie in', () => {
    const lang = { beurt: 1, vraag: 'Hoeveel studenten heeft de universiteit in totaal ingeschreven staan per jaar?' }
    const notitie = voortbouwNotitie({ beurt: 2, bouwt_voort_op: [1] }, [lang])
    expect(notitie).toContain('…”')
    expect(notitie.length).toBeLessThan(lang.vraag.length + 40)
  })
})
