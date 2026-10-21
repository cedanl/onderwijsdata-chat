// @vitest-environment jsdom
// #648: een tik op "Genereer rapport" deed soms stil niets. generateReport keerde zonder melding terug tijdens een
// lopend antwoord, stuurde over een socket die niet open was, en een weigering van de server (busy, of error bij de
// verzoeklimiet) liet de knop tot de time-out op "wordt gegenereerd" staan. Nu geeft elke tik een uitkomst.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useChat, REPORT_TIMEOUT_MS, REASON_TOAST_MS } from '../hooks/useChat'
import { BACKOFF_DELAYS } from '../socketHealth'
import { FakeWebSocket } from './fakeWebSocket'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

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

const rapportFrames = ws => ws.sent.filter(m => m.action === 'generate_report')
const toastTeksten = () => chat.toasts.map(t => t.message)

async function vraag(ws) {
  let verstuurd
  await act(async () => { verstuurd = chat.generateReport('tester') })
  return { verstuurd, frames: rapportFrames(ws).length }
}

beforeEach(() => {
  FakeWebSocket.reset()
  globalThis.WebSocket = FakeWebSocket
})

afterEach(() => {
  if (root) act(() => root.unmount())
  root = null
  vi.useRealTimers()
})

describe('generateReport kan niet starten (#648)', () => {
  it('tijdens een lopend antwoord: geen frame, geen wachten, wel de reden', async () => {
    const ws = await mount()
    await act(async () => { ws.emit({ type: 'message_start' }) })

    const { verstuurd, frames } = await vraag(ws)

    expect(verstuurd).toBe(false)
    expect(frames).toBe(0)
    expect(chat.reportBusy).toBe(false)
    expect(toastTeksten().some(t => t.includes('Wacht tot het antwoord klaar is'))).toBe(true)
  })

  it('ook vóór het eerste bericht van een verstuurde vraag', async () => {
    const ws = await mount()
    await act(async () => { chat.send('Hoeveel mbo-studenten?') })

    const { frames } = await vraag(ws)

    expect(frames).toBe(0)
    expect(toastTeksten()).toContain('Wacht tot het antwoord klaar is')
  })

  it('met een socket die nog niet open is: gooit niet, stuurt niets en noemt de verbinding', async () => {
    const ws = await mount({ open: false })
    expect(ws.readyState).toBe(FakeWebSocket.CONNECTING)

    let verstuurd
    await act(async () => { expect(() => { verstuurd = chat.generateReport('tester') }).not.toThrow() })

    expect(verstuurd).toBe(false)
    expect(ws.sent).toEqual([])
    expect(chat.reportBusy).toBe(false)
    expect(toastTeksten().some(t => /verbinding/i.test(t))).toBe(true)
  })

  it('met een socket die al sluit: stuurt niets en noemt de verbinding', async () => {
    const ws = await mount()
    ws.close()
    expect(ws.readyState).toBe(FakeWebSocket.CLOSING)

    const { frames } = await vraag(ws)

    expect(frames).toBe(0)
    expect(chat.reportBusy).toBe(false)
    expect(toastTeksten().some(t => /verbinding/i.test(t))).toBe(true)
  })

  it('terwijl een nieuw gesprek start', async () => {
    const ws = await mount()
    await act(async () => { chat.startNewConversation() })
    expect(chat.resetting).toBe(true)

    const { verstuurd, frames } = await vraag(ws)

    expect(verstuurd).toBe(false)
    expect(frames).toBe(0)
    expect(chat.reportBusy).toBe(false)
    expect(toastTeksten()).toContain('Even wachten: het nieuwe gesprek wordt gestart')
  })

  it('een tweede tik terwijl het rapport loopt stuurt geen tweede frame', async () => {
    const ws = await mount()
    expect((await vraag(ws)).verstuurd).toBe(true)
    await act(async () => { ws.emit({ type: 'report_generating' }) })

    const { verstuurd, frames } = await vraag(ws)

    expect(verstuurd).toBe(false)
    expect(frames).toBe(1)
    expect(chat.reportBusy).toBe(true)
    expect(toastTeksten()).toContain('Er wordt al een rapport gemaakt')
  })

  it('ook vóór report_generating geen tweede frame', async () => {
    const ws = await mount()
    await vraag(ws)
    const { frames } = await vraag(ws)
    expect(frames).toBe(1)
    expect(toastTeksten()).toContain('Er wordt al een rapport gemaakt')
  })

  it('zegt dat je opnieuw moet tikken: zonder verbinding start het rapport niet vanzelf', async () => {
    const ws = await mount({ open: false })
    await vraag(ws)
    expect(toastTeksten()).toEqual(['Geen verbinding: tik opnieuw zodra de verbinding terug is'])
  })

  it('snel herhaalde tikken met dezelfde reden geven één melding; na die melding weer een nieuwe', async () => {
    vi.useFakeTimers()
    const ws = await mount({ open: false })

    for (let i = 0; i < 3; i++) await vraag(ws)
    expect(toastTeksten()).toHaveLength(1)

    await act(async () => { vi.advanceTimersByTime(REASON_TOAST_MS) })
    expect(chat.toasts).toEqual([])
    await vraag(ws)
    expect(toastTeksten()).toHaveLength(1)
    expect(ws.sent).toEqual([])
  })

  it('een andere reden krijgt wel een eigen melding', async () => {
    const ws = await mount()
    await vraag(ws)
    await vraag(ws)
    await act(async () => { ws.emit({ type: 'report_ready', spec: { titel: 'R' } }) })
    await act(async () => { ws.emit({ type: 'message_start' }) })
    await vraag(ws)
    expect(toastTeksten()).toEqual(['Er wordt al een rapport gemaakt', 'Wacht tot het antwoord klaar is'])
  })

  it('start wel als alles klaar is, zonder melding', async () => {
    const ws = await mount()
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'Klaar.' })
    })

    const { verstuurd, frames } = await vraag(ws)

    expect(verstuurd).toBe(true)
    expect(frames).toBe(1)
    expect(chat.reportBusy).toBe(true)
    expect(chat.toasts).toEqual([])
  })
})

describe('de server weigert het rapport (#648)', () => {
  it.each([
    ['busy', { type: 'busy', message: 'Er loopt nog een antwoord. Stop dat eerst of wacht even.' }],
    ['error', { type: 'error', message: 'Te veel verzoeken in korte tijd. Probeer het over 42 seconden opnieuw.', modelafhankelijk: false }],
  ])('%s vóór report_generating beëindigt het wachten meteen en toont de melding', async (_naam, weigering) => {
    const ws = await mount()
    await vraag(ws)
    expect(chat.reportBusy).toBe(true)

    await act(async () => { ws.emit(weigering) })

    expect(chat.reportBusy).toBe(false)
    expect(toastTeksten()).toContain(weigering.message)
    // Geen foutbericht in de chat: de melding hoort bij de tik, niet bij het gesprek.
    expect(chat.messages).toEqual([])

    // De volgende tik stuurt weer een frame.
    const { verstuurd, frames } = await vraag(ws)
    expect(verstuurd).toBe(true)
    expect(frames).toBe(2)
  })

  it.each(['busy', 'error'])('na een %s loopt de time-out van dat rapport niet meer', async type => {
    vi.useFakeTimers()
    const ws = await mount()
    await vraag(ws)
    await act(async () => { ws.emit({ type, message: 'geweigerd' }) })

    await act(async () => { vi.advanceTimersByTime(REPORT_TIMEOUT_MS + 1) })

    expect(chat.messages).toEqual([])
    expect(ws.sent).not.toContainEqual({ action: 'stop' })
  })

  it('een weigering zonder tekst krijgt een eigen melding', async () => {
    const ws = await mount()
    await vraag(ws)
    await act(async () => { ws.emit({ type: 'error' }) })
    expect(chat.reportBusy).toBe(false)
    expect(toastTeksten()).toEqual(['Het rapport kon nu niet starten. Probeer het zo opnieuw.'])
  })

  it('na report_generating is een error van de lopende run geen weigering: het rapport loopt door', async () => {
    const ws = await mount()
    await vraag(ws)
    await act(async () => {
      ws.emit({ type: 'report_generating' })
      ws.emit({ type: 'error', message: 'stap mislukt' })
    })
    expect(chat.reportBusy).toBe(true)
    expect(chat.messages).toEqual([])

    await act(async () => { ws.emit({ type: 'report_ready', spec: { titel: 'R' } }) })
    expect(chat.reportBusy).toBe(false)
    expect(chat.reportSpec).toEqual({ titel: 'R' })
  })

  it('na een herverbinding vuurt de time-out van het verloren rapport niet meer', async () => {
    vi.useFakeTimers()
    const ws = await mount()
    await vraag(ws)
    await act(async () => { ws.close(); ws.finishClose() })
    await act(async () => { vi.advanceTimersByTime(Math.max(...BACKOFF_DELAYS) + 1) })
    const nieuw = FakeWebSocket.last
    expect(nieuw).not.toBe(ws)
    await act(async () => { nieuw.open() })
    expect(chat.reportBusy).toBe(false)

    await act(async () => { vi.advanceTimersByTime(REPORT_TIMEOUT_MS + 1) })

    // Alleen de melding van het verbindingsverlies, geen time-outbericht en geen stop naar de nieuwe sessie.
    expect(chat.messages.map(m => m.content)).toEqual([
      'De verbinding viel weg tijdens het maken van het rapport. Probeer het opnieuw.',
    ])
    expect(FakeWebSocket.instances.flatMap(s => s.sent)).not.toContainEqual({ action: 'stop' })
  })

  it('een busy op een gewone vraag gaat nog naar de vraag terug, niet naar het rapport', async () => {
    const ws = await mount()
    await act(async () => { chat.send('Tweede vraag') })
    await act(async () => { ws.emit({ type: 'busy', message: 'Er loopt nog iets.' }) })
    expect(chat.busy).toBe(false)
    expect(chat.rejectedDraft).toBe('Tweede vraag')
    expect(chat.reportBusy).toBe(false)
  })
})
