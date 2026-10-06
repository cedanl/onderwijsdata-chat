// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useChat, REPORT_TIMEOUT_MS } from '../hooks/useChat'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

class FakeWebSocket {
  static OPEN = 1
  static last = null
  constructor() {
    this.readyState = FakeWebSocket.OPEN
    this.sent = []
    FakeWebSocket.last = this
  }
  send(data) { this.sent.push(JSON.parse(data)) }
  close() {}
  emit(event) { this.onmessage({ data: JSON.stringify(event) }) }
}

let root
let container
let chat

function Harness() {
  chat = useChat()
  return null
}

beforeEach(async () => {
  globalThis.WebSocket = FakeWebSocket
  container = document.createElement('div')
  root = createRoot(container)
  await act(async () => { root.render(createElement(Harness)) })
})

afterEach(() => {
  act(() => root.unmount())
})

const assistantMessages = () => chat.messages.filter(m => m.role === 'assistant')

describe('useChat streaming', () => {
  it('keeps every delta when message_end arrives in the same batch', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'D' })
      ws.emit({ type: 'text_delta', content: 'U' })
      ws.emit({ type: 'text_delta', content: 'O' })
      ws.emit({ type: 'message_end', content: 'DUO' })
    })
    const [msg] = assistantMessages()
    expect(msg.content).toBe('DUO')
    expect(msg.done).toBe(true)
  })

  it('treats message_end content as the final text', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { ws.emit({ type: 'message_start' }) })
    await act(async () => { ws.emit({ type: 'text_delta', content: 'de registratie van' }) })
    await act(async () => {
      ws.emit({ type: 'message_end', content: 'de registratie van studiekeuze en -financiering.' })
    })
    expect(assistantMessages()[0].content).toBe('de registratie van studiekeuze en -financiering.')
  })

  it('applies late updates to their own message when the next one has started', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'eerste' })
      ws.emit({ type: 'message_end', content: 'eerste' })
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'tweede' })
      ws.emit({ type: 'message_end', content: 'tweede' })
    })
    expect(assistantMessages().map(m => m.content)).toEqual(['eerste', 'tweede'])
    expect(assistantMessages().every(m => m.done)).toBe(true)
  })
})

describe('useChat report errors', () => {
  it('shows a report error as a lasting chat message, not a toast', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'report_generating' })
      ws.emit({ type: 'report_error', message: 'Rapport kon niet worden gemaakt. Probeer het opnieuw.' })
    })
    const [msg] = assistantMessages()
    expect(msg.content).toBe('Rapport kon niet worden gemaakt. Probeer het opnieuw.')
    expect(msg.isError).toBe(true)
    expect(chat.toasts).toEqual([])
    expect(chat.reportBusy).toBe(false)
  })

  // #219: report_ready never came, and the button kept saying "wordt gegenereerd" for good.
  describe('when report_ready never comes', () => {
    afterEach(() => vi.useRealTimers())

    it('ends the wait after the timeout with a message, stops the server and frees the button', async () => {
      vi.useFakeTimers()
      const ws = FakeWebSocket.last
      await act(async () => { chat.generateReport('tester') })
      await act(async () => { ws.emit({ type: 'report_generating' }) })
      expect(chat.reportBusy).toBe(true)

      await act(async () => { vi.advanceTimersByTime(REPORT_TIMEOUT_MS - 1) })
      expect(chat.reportBusy).toBe(true)
      await act(async () => { vi.advanceTimersByTime(1) })

      expect(chat.reportBusy).toBe(false)
      const [msg] = assistantMessages()
      expect(msg.isError).toBe(true)
      expect(msg.content).toMatch(/rapport.*niet.*klaar.*opnieuw/is)
      expect(ws.sent).toContainEqual({ action: 'stop' })
    })

    it('ignores what the stopped server still sends after the timeout', async () => {
      vi.useFakeTimers()
      const ws = FakeWebSocket.last
      await act(async () => { chat.generateReport('tester') })
      await act(async () => { vi.advanceTimersByTime(REPORT_TIMEOUT_MS) })
      await act(async () => {
        ws.emit({ type: 'report_error', message: 'Rapport kon niet worden gemaakt. Probeer het opnieuw.' })
        ws.emit({ type: 'report_ready', spec: { titel: 'te laat' } })
      })

      expect(assistantMessages()).toHaveLength(1)
      expect(chat.reportSpec).toBeNull()
    })

    it('does not fire after the report arrived in time', async () => {
      vi.useFakeTimers()
      const ws = FakeWebSocket.last
      await act(async () => { chat.generateReport('tester') })
      await act(async () => { ws.emit({ type: 'report_ready', spec: { titel: 'R' } }) })
      await act(async () => { vi.advanceTimersByTime(REPORT_TIMEOUT_MS * 2) })

      expect(chat.reportSpec).toEqual({ titel: 'R' })
      expect(assistantMessages()).toEqual([])
      expect(ws.sent).not.toContainEqual({ action: 'stop' })
    })

    it('says so when the connection drops while the report is being made', async () => {
      const ws = FakeWebSocket.last
      await act(async () => { chat.generateReport('tester') })
      await act(async () => {
        ws.readyState = 3
        ws.onclose({ code: 1006 })
      })

      expect(chat.reportBusy).toBe(false)
      expect(assistantMessages()[0].content).toMatch(/verbinding.*rapport/is)
    })
  })
})

// #339: a report takes one to two minutes; the wait shows progress and can be cancelled.
describe('useChat report progress and cancel', () => {
  it('counts the steps of the report run without putting them in the chat', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { chat.generateReport('tester') })
    await act(async () => {
      ws.emit({ type: 'report_generating' })
      ws.emit({ type: 'tool_start', name: 'query_data', label: 'Data opvragen' })
      ws.emit({ type: 'tool_end', name: 'query_data', output: '' })
      ws.emit({ type: 'tool_start', name: 'create_plot', label: 'Grafiek maken' })
    })
    expect(chat.reportProgress).toEqual({ steps: 2, label: 'Grafiek maken' })
    expect(chat.messages).toEqual([])
  })

  it('starts counting afresh for the next report', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { chat.generateReport('tester') })
    await act(async () => { ws.emit({ type: 'tool_start', name: 'query_data', label: 'Data opvragen' }) })
    await act(async () => { ws.emit({ type: 'report_ready', spec: { titel: 'R' } }) })
    await act(async () => { chat.generateReport('tester') })
    expect(chat.reportProgress).toEqual({ steps: 0, label: null })
  })

  it('cancelling stops the server and frees the button at once', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { chat.generateReport('tester') })
    await act(async () => { chat.cancelReport() })

    expect(ws.sent).toContainEqual({ action: 'stop' })
    expect(chat.reportBusy).toBe(false)
    expect(chat.reportSpec).toBeNull()
    expect(assistantMessages().filter(m => m.isError)).toEqual([])
  })

  it('ignores what the cancelled run still sends until the server confirms', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { chat.generateReport('tester') })
    await act(async () => { chat.cancelReport() })
    await act(async () => {
      ws.emit({ type: 'tool_start', name: 'create_plot', label: 'Grafiek maken' })
      ws.emit({ type: 'report_ready', spec: { titel: 'te laat' } })
    })
    expect(chat.messages).toEqual([])
    expect(chat.reportSpec).toBeNull()

    await act(async () => { ws.emit({ type: 'report_cancelled' }) })
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'volgende vraag' })
    })
    expect(assistantMessages().map(m => m.content)).toEqual(['volgende vraag'])
  })

  it('a stop from elsewhere ends the wait without an error', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { chat.generateReport('tester') })
    await act(async () => { ws.emit({ type: 'report_cancelled' }) })
    expect(chat.reportBusy).toBe(false)
    expect(assistantMessages()).toEqual([])
  })
})

describe('useChat stop', () => {
  it('marks an aborted answer as stopped and keeps its partial text', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'Half antwoord' })
      ws.emit({ type: 'message_end', aborted: true })
    })
    const [msg] = assistantMessages()
    expect(msg.content).toBe('Half antwoord')
    expect(msg.stopped).toBe(true)
    expect(msg.done).toBe(true)
  })

  it('marks an answer that hit the output limit as truncated', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'Conclusie – niet beschikbaar in de', truncated: true })
    })
    expect(assistantMessages()[0].truncated).toBe(true)
  })

  it('keeps what the server check still found wrong on the answer', async () => {
    // #185, #187: a problem that survived the correction round stays visible.
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'Toch 6.340.', controle: ['6.340 staat niet in de opgehaalde data.'] })
    })
    expect(assistantMessages()[0].controle).toEqual(['6.340 staat niet in de opgehaalde data.'])
  })

  it('drops the unchecked answer when the server withdraws it for a correction', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'In totaal 6.340.' })
      ws.emit({ type: 'message_cancel' })
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'In totaal 5.943.' })
    })
    expect(assistantMessages().map(m => m.content)).toEqual(['In totaal 5.943.'])
  })

  it('marks a final answer without any text as empty', async () => {
    // Live-audit 6: message_end without text left a silent, invisible turn.
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: '' })
    })
    expect(assistantMessages()[0]).toMatchObject({ empty: true, done: true })
  })

  it('does not mark a stopped answer without text as empty', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', aborted: true })
    })
    const [msg] = assistantMessages()
    expect(msg.stopped).toBe(true)
    expect(msg.empty).toBeUndefined()
  })

  it('does not mark a normal answer as stopped', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'Klaar' })
    })
    expect(assistantMessages()[0].stopped).toBeFalsy()
  })
})

describe('useChat new conversation', () => {
  it('asks the server for a fresh session and holds messages until it confirms', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { chat.startNewConversation() })
    expect(ws.sent).toContainEqual({ action: 'reset' })
    expect(chat.resetting).toBe(true)

    await act(async () => { chat.send('Welke afkorting noemde ik eerder?') })
    expect(ws.sent.filter(m => m.action === 'message')).toEqual([])

    await act(async () => { ws.emit({ type: 'reset_done' }) })
    expect(chat.resetting).toBe(false)
    await act(async () => { chat.send('Welke afkorting noemde ik eerder?') })
    expect(ws.sent.filter(m => m.action === 'message')).toHaveLength(1)
  })

  it('clears the visible messages', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'oud antwoord' })
    })
    await act(async () => { chat.startNewConversation() })
    expect(chat.messages).toEqual([])
  })

  // #337: "Nieuw gesprek" during a run refused the next question until the old run ended.
  it('sends a question right after a reset that interrupted a run', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { chat.send('Hoeveel studenten heeft de HU?') })
    await act(async () => { ws.emit({ type: 'message_start' }) })
    await act(async () => { chat.startNewConversation() })
    await act(async () => { ws.emit({ type: 'reset_done' }) })
    expect(chat.busy).toBe(false)

    let sent
    await act(async () => { sent = chat.send('Hoeveel eerstejaars heeft de UU?') })
    expect(sent).toBe(true)
    expect(ws.sent.filter(m => m.action === 'message')).toHaveLength(2)
  })

  it('drops stream events of the old run that arrive before reset_done', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { chat.send('Hoeveel studenten heeft de HU?') })
    await act(async () => { ws.emit({ type: 'message_start' }) })
    await act(async () => { chat.startNewConversation() })
    await act(async () => {
      ws.emit({ type: 'text_delta', content: 'oud' })
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'reset_done' })
    })
    expect(chat.messages).toEqual([])
  })
})

describe('useChat connection loss', () => {
  const drop = async (ws) => {
    await act(async () => {
      ws.readyState = 3
      ws.onclose({ code: 1006 })
    })
  }

  afterEach(() => vi.useRealTimers())

  it('ends a half-streamed answer visibly and accepts the next question after reconnecting', async () => {
    vi.useFakeTimers()
    const ws = FakeWebSocket.last
    await act(async () => {
      chat.send('Eerste vraag')
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'Half' })
    })
    await drop(ws)

    const [msg] = assistantMessages()
    expect(msg).toMatchObject({ content: 'Half', done: true, interrupted: true })
    expect(chat.busy).toBe(false)
    expect(chat.thinking).toBe(false)

    await act(async () => { vi.advanceTimersByTime(1000) })
    const reconnected = FakeWebSocket.last
    expect(reconnected).not.toBe(ws)
    await act(async () => { reconnected.onopen() })
    let accepted
    await act(async () => { accepted = chat.send('Tweede vraag') })
    expect(accepted).toBe(true)
    expect(reconnected.sent).toContainEqual({ action: 'message', content: 'Tweede vraag' })
  })

  it('tells the user when a question got no answer before the connection dropped', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { chat.send('Vraag') })
    await drop(ws)
    const [msg] = assistantMessages()
    expect(msg.isError).toBe(true)
    expect(chat.busy).toBe(false)
  })

  it('also recovers when the answer to a clarification choice is cut off', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      chat.sendClarification('HBO')
      ws.emit({ type: 'message_start' })
    })
    await drop(ws)
    expect(chat.busy).toBe(false)
    expect(assistantMessages()[0].interrupted).toBe(true)
  })

  it('refuses to send while the connection is down', async () => {
    const ws = FakeWebSocket.last
    await drop(ws)
    let accepted
    await act(async () => { accepted = chat.send('Vraag') })
    expect(accepted).toBe(false)
    expect(chat.messages).toEqual([])
  })
})

describe('useChat busy refusal (#145)', () => {
  it('shows the notice, removes the refused question and hands it back as a draft', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { await Promise.resolve() })
    await act(async () => { chat.send('Tweede vraag') })
    expect(chat.messages.some(m => m.role === 'user' && m.content === 'Tweede vraag')).toBe(true)

    await act(async () => {
      ws.emit({ type: 'busy', message: 'Er loopt nog een antwoord. Stop dat eerst of wacht even.' })
    })

    expect(chat.messages.some(m => m.role === 'user')).toBe(false)
    expect(chat.rejectedDraft).toBe('Tweede vraag')
    expect(chat.toasts.map(t => t.message)).toContain('Er loopt nog een antwoord. Stop dat eerst of wacht even.')
    expect(chat.thinking).toBe(false)
  })

  it('does not hand back a question the server accepted', async () => {
    const ws = FakeWebSocket.last
    await act(async () => { chat.send('Eerste vraag') })
    await act(async () => { ws.emit({ type: 'message_start' }) })
    await act(async () => { ws.emit({ type: 'busy', message: 'x' }) })

    expect(chat.rejectedDraft).toBeNull()
    expect(chat.messages.some(m => m.role === 'user' && m.content === 'Eerste vraag')).toBe(true)
  })
})

describe('useChat reasoning steps (#76)', () => {
  it('keeps the tool steps of consecutive model rounds in one message', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'tool_start', name: 'search_catalog', label: 'Catalogus' })
      ws.emit({ type: 'tool_end', name: 'search_catalog' })
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'tool_start', name: 'get_duo_data', label: 'DUO' })
      ws.emit({ type: 'tool_end', name: 'get_duo_data', snippet: 'df = 1' })
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'Antwoord.' })
      ws.emit({ type: 'message_end', content: 'Antwoord.' })
    })
    const [msg, ...rest] = assistantMessages()
    expect(rest).toHaveLength(0)
    expect(msg.tools.map(t => t.name)).toEqual(['search_catalog', 'get_duo_data'])
    expect(msg.tools.every(t => t.done)).toBe(true)
    expect(msg.tools[1].snippet).toBe('df = 1')
    expect(msg.content).toBe('Antwoord.')
  })

  it('keeps text from a tool round out of the answer, in the same reasoning card (#393)', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'We need to capture the result. ' })
      ws.emit({ type: 'tool_start', name: 'run_analysis', label: 'Analyse' })
      ws.emit({ type: 'tool_end', name: 'run_analysis', output: '' })
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'text_delta', content: 'Samenvatting' })
      ws.emit({ type: 'message_end', content: 'Samenvatting' })
    })
    const [antwoord, ...rest] = assistantMessages()
    expect(rest).toEqual([])
    expect(antwoord.content).toBe('Samenvatting')
    expect(antwoord.tussentekst).toEqual(['We need to capture the result. '])
    expect(antwoord.tools.map(t => t.name)).toEqual(['run_analysis'])
  })

  it('finishes the right step when the same tool runs twice', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'tool_start', name: 'query_data', label: 'Query' })
      ws.emit({ type: 'tool_start', name: 'query_data', label: 'Query' })
      ws.emit({ type: 'tool_end', name: 'query_data', snippet: 'eerste' })
    })
    expect(assistantMessages()[0].tools.map(t => [t.done, t.snippet ?? null])).toEqual([[true, 'eerste'], [false, null]])
  })

  it('keeps the outcome of a step, so an empty filter is not shown as a success (#386)', async () => {
    const ws = FakeWebSocket.last
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'tool_start', name: 'query_data', label: 'Data gefilterd' })
      ws.emit({
        type: 'tool_end', name: 'query_data', status: 'empty',
        status_label: 'Filter leverde 0 rijen op', suggesties: { Niveau: ['Hbo', 'Wo'] },
      })
    })
    const [step] = assistantMessages()[0].tools
    expect(step).toMatchObject({ done: true, status: 'empty', statusLabel: 'Filter leverde 0 rijen op', suggesties: { Niveau: ['Hbo', 'Wo'] } })
  })
})

describe('useChat question model', () => {
  it('records on each question the model it was sent with (#242)', async () => {
    await act(async () => { chat.sendSettings({ model: 'anthropic/claude-opus' }) })
    await act(async () => { chat.send('Hoeveel eerstejaars?') })
    await act(async () => { FakeWebSocket.last.emit({ type: 'message_end', content: 'Veel.' }) })
    await act(async () => { chat.sendSettings({ model: 'openai/gpt-oss-120b' }) })
    await act(async () => { chat.sendClarification('HBO') })
    const questions = chat.messages.filter(m => m.role === 'user')
    expect(questions.map(m => m.model)).toEqual(['anthropic/claude-opus', 'openai/gpt-oss-120b'])
  })
})
