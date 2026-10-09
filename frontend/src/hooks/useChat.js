import { useState, useEffect, useRef, useCallback } from 'react'
import { chatSocket, clearToken } from '../auth'
import { MAX_HISTORY } from '../constants'
import { finishStep } from '../toolSteps'
import { closeWithoutText, withdrawText } from '../turnTrace'

const BACKOFF_DELAYS = [1000, 2000, 4000, 8000, 16000]
const MAX_RETRIES = 4
// A report without report_ready after this long counts as failed (#219). Reports take
// around five minutes (#417); the server has no limit of its own, so the wait ends here.
export const REPORT_TIMEOUT_MS = 10 * 60 * 1000

// A clarification question stays in: without it a restored choice ("2023/24") answers nothing (#109).
export function buildHistory(messages) {
  return messages
    .filter(m =>
      (m.role === 'user' || m.role === 'assistant') &&
      m.content &&
      !m.isError &&
      !m.figures &&
      !m.starterQuestions
    )
    .map(({ role, content }) => ({ role, content }))
    .slice(-MAX_HISTORY)
}

const NO_REPORT_PROGRESS = { steps: 0, label: null }

export function useChat({ onUnauthorized } = {}) {
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [thinking, setThinking] = useState(false)
  const [toasts, setToasts] = useState([])
  const [connected, setConnected] = useState(false)
  const [reportBusy, setReportBusy] = useState(false)
  const [reportSpec, setReportSpec] = useState(null)
  // Steps of the report run, shown while the report is being made (#339).
  const [reportProgress, setReportProgress] = useState(NO_REPORT_PROGRESS)
  const [resetting, setResetting] = useState(false)
  const [rejectedDraft, setRejectedDraft] = useState(null)
  const wsRef = useRef(null)
  const currentMsgRef = useRef(null)
  const reportingRef = useRef(false)
  const pendingSettingsRef = useRef(null)
  // Each question records the model it went out with, so a reopened conversation can resume it (#242).
  const modelRef = useRef(null)
  const idRef = useRef(0)
  const manualCloseRef = useRef(false)
  const retryCountRef = useRef(0)
  const retryTimeoutRef = useRef(null)
  const pendingHistoryRef = useRef(null)
  const busyRef = useRef(false)
  const lastSentRef = useRef(null)
  const currentHasTextRef = useRef(false)
  const resettingRef = useRef(false)
  const reportTimeoutRef = useRef(null)
  // A report run that was stopped but not yet ended by the server: what it still sends is dropped.
  const reportAbandonedRef = useRef(false)
  const nextId = () => ++idRef.current

  // The report is over, with or without a result: no more waiting, button free again.
  const endReport = useCallback(() => {
    clearTimeout(reportTimeoutRef.current)
    reportTimeoutRef.current = null
    reportingRef.current = false
    setReportBusy(false)
  }, [])

  // A failed report stays visible as a chat message; the button is the retry (#219).
  // Stop the report run: nothing it still sends may reach the user, until the server ends it.
  const abandonReport = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ action: 'stop' }))
    reportAbandonedRef.current = true
    endReport()
    setReportSpec(null)
  }, [endReport])

  const failReport = useCallback((message) => {
    endReport()
    setReportSpec(null)
    setMessages(prev => [...prev, { id: ++idRef.current, role: 'assistant', content: message, done: true, isError: true }])
  }, [endReport])

  const addToast = useCallback((message, level = 'info') => {
    const id = nextId()
    setToasts(t => [...t, { id, message, level }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000)
  }, [])

  // The open card ends without an answer: its steps stay as the turn's trace (#398).
  const closeCurrentMsg = useCallback(() => {
    if (!currentMsgRef.current) return
    const id = currentMsgRef.current
    setMessages(prev => prev.flatMap(m => m.id !== id ? [m] : (closeWithoutText(m) ?? [])))
    currentMsgRef.current = null
  }, [])

  useEffect(() => {
    manualCloseRef.current = false
    retryCountRef.current = 0

    // Resolve the target id now: React runs the state updater later, by which
    // time message_end may already have cleared currentMsgRef.
    function updateCurrentMsg(updater) {
      const id = currentMsgRef.current
      if (id === null) return
      setMessages(prev => prev.map(m => m.id === id ? updater(m) : m))
    }

    function finishStream() {
      currentMsgRef.current = null
      busyRef.current = false
      setBusy(false)
    }

    // The server session is gone with its socket, and so is the answer it was writing.
    function endInterruptedTurn() {
      if (!busyRef.current) return
      if (currentMsgRef.current) {
        updateCurrentMsg(m => ({ ...m, done: true, interrupted: true }))
      } else {
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant', done: true, isError: true,
          content: 'De verbinding viel weg voordat er een antwoord kwam. Stel je vraag opnieuw.',
        }])
      }
      setThinking(false)
      finishStream()
    }

    const messageHandlers = {
      system_message(ev) {
        addToast(ev.message, 'warning')
      },
      toast(ev) {
        addToast(ev.message, ev.level || 'info')
      },
      // The server refused a question because a run is still going (#145): say so,
      // take the question back out of the transcript and give it back to the input.
      busy(ev) {
        addToast(ev.message, 'warning')
        const sent = lastSentRef.current
        lastSentRef.current = null
        setThinking(false)
        if (!sent) return
        // The refused question never became a run: nothing will end it, so the chat is free (#417).
        finishStream()
        setMessages(prev => prev.filter(m => m.id !== sent.id))
        if (sent.draft) setRejectedDraft(sent.content)
      },
      message_start() {
        lastSentRef.current = null
        setThinking(false)
        // Every model round announces itself. A round before the last one called tools: its
        // steps belong in the same reasoning card as the next round's (#76), and what it
        // wrote on the way ('We need to capture the result…') is no answer (#393).
        if (currentMsgRef.current !== null) {
          if (currentHasTextRef.current) {
            updateCurrentMsg(m => ({ ...m, content: '', tussentekst: [...(m.tussentekst || []), m.content] }))
            currentHasTextRef.current = false
          }
          return
        }
        currentHasTextRef.current = false
        const msgId = nextId()
        currentMsgRef.current = msgId
        setMessages(prev => [...prev, { id: msgId, role: 'assistant', content: '', tools: [], done: false }])
      },
      // The answer was withdrawn (correction or clarification): the next round writes on in
      // the same card, so the steps before and after the correction stay together (#398).
      message_cancel(ev) {
        currentHasTextRef.current = false
        updateCurrentMsg(m => withdrawText(m, ev.reden))
      },
      text_delta(ev) {
        currentHasTextRef.current = true
        setThinking(false)
        updateCurrentMsg(m => ({ ...m, content: m.content + ev.content }))
      },
      tool_start(ev) {
        setThinking(false)
        updateCurrentMsg(m => ({
          ...m, tools: [...m.tools, { name: ev.name, label: ev.label, done: false }],
        }))
      },
      tool_end(ev) {
        updateCurrentMsg(m => ({
          ...m,
          // The first step of this name still running: the same tool can run twice in one card.
          tools: m.tools.map((t, i, all) =>
            t.name === ev.name && !t.done && all.findIndex(x => x.name === ev.name && !x.done) === i
              ? finishStep(t, ev)
              : t
          ),
        }))
      },
      figure(ev) {
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant',
          content: '', figures: [{ label: ev.label, json: ev.figure_json }], done: true,
        }])
      },
      message_end(ev) {
        // The server sends the full text; it wins over the accumulated deltas.
        updateCurrentMsg(m => {
          const content = typeof ev.content === 'string' ? ev.content : m.content
          return {
            ...m,
            content,
            done: true,
            ...(ev.aborted && { stopped: true }),
            ...(ev.truncated && { truncated: true }),
            // Step budget spent: a partial answer, which another model often completes (#405).
            ...(ev.partial && { partial: true }),
            // What the server's check on this answer still found wrong (#185, #187).
            ...(ev.controle?.length && { controle: ev.controle }),
            // Sentences in which the model revised itself go to the reasoning card, not the answer (#412).
            ...(ev.tussentekst?.length && { tussentekst: [...(m.tussentekst || []), ...ev.tussentekst] }),
            // The numbers that passed the check, each with the step it came from (#365).
            ...(ev.citaties?.length && { citaties: ev.citaties }),
            // The sources the server derived from the steps, also when empty: they mark a data answer (#416).
            ...(Array.isArray(ev.bronnen) && { bronnen: ev.bronnen }),
            // A finished turn without text would otherwise render nothing at all.
            ...(!content.trim() && !ev.aborted && { empty: true }),
          }
        })
        finishStream()
      },
      clarification(ev) {
        setThinking(false)
        closeCurrentMsg()
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant',
          content: ev.vraag, clarification: ev.opties, done: true,
        }])
        finishStream()
      },
      starter_questions(ev) {
        setThinking(false)
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant',
          content: `Hier zijn voorbeeldvragen over **${ev.label}**:`,
          starterQuestions: ev.questions, done: true,
        }])
        finishStream()
      },
      reset_done() {
        resettingRef.current = false
        setResetting(false)
      },
      report_generating() {
        reportingRef.current = true
        setReportBusy(true)
        setReportSpec(null)
      },
      report_cancelled() {
        if (reportingRef.current) endReport()
      },
      // Not waiting any more (timed out, see generateReport): the user has been told already.
      report_ready(ev) {
        if (!reportingRef.current) return
        endReport()
        setReportSpec(ev.spec)
      },
      report_error(ev) {
        if (!reportingRef.current) return
        failReport(ev.message)
      },
      error(ev) {
        setThinking(false)
        closeCurrentMsg()
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant', content: ev.message, done: true, isError: true,
          modelafhankelijk: ev.modelafhankelijk !== false,
        }])
        busyRef.current = false
        setBusy(false)
      },
    }

    const chatStreamEvents = new Set([
      'message_start', 'message_cancel', 'text_delta', 'tool_start',
      'tool_end', 'figure', 'message_end', 'clarification', 'starter_questions', 'error',
    ])
    const reportEndEvents = new Set(['report_ready', 'report_error', 'report_cancelled'])

    function connect() {
      const ws = chatSocket()
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        // A new connection is a new server session, so a pending reset is moot.
        resettingRef.current = false
        setResetting(false)
        retryCountRef.current = 0
        reportingRef.current = false
        reportAbandonedRef.current = false
        setReportBusy(false)
        setReportSpec(null)
        if (pendingHistoryRef.current?.length > 0) {
          ws.send(JSON.stringify({ action: 'history', messages: pendingHistoryRef.current }))
          pendingHistoryRef.current = null
        }
        if (pendingSettingsRef.current) {
          ws.send(JSON.stringify({ action: 'settings', settings: pendingSettingsRef.current }))
          pendingSettingsRef.current = null
        }
      }

      ws.onclose = (e) => {
        setConnected(false)
        endInterruptedTurn()
        if (reportingRef.current) {
          failReport('De verbinding viel weg tijdens het maken van het rapport. Probeer het opnieuw.')
        }

        if (e.code === 4001) {
          clearToken()
          onUnauthorized?.()
          return
        }

        if (manualCloseRef.current) return

        if (retryCountRef.current < MAX_RETRIES) {
          const delay = BACKOFF_DELAYS[retryCountRef.current] ?? BACKOFF_DELAYS[BACKOFF_DELAYS.length - 1]
          retryCountRef.current += 1
          retryTimeoutRef.current = setTimeout(() => {
            if (!manualCloseRef.current) connect()
          }, delay)
        }
      }

      ws.onmessage = (e) => {
        const event = JSON.parse(e.data)
        if (reportAbandonedRef.current) {
          if (reportEndEvents.has(event.type)) reportAbandonedRef.current = false
          if (reportEndEvents.has(event.type) || chatStreamEvents.has(event.type)) return
        }
        if (reportingRef.current && chatStreamEvents.has(event.type)) {
          if (event.type === 'tool_start') {
            setReportProgress(p => ({ steps: p.steps + 1, label: event.label || null }))
          }
          return
        }
        // Until reset_done, stream events belong to the run of the conversation that was just left (#337).
        if (resettingRef.current && chatStreamEvents.has(event.type)) return
        const handler = messageHandlers[event.type]
        if (handler) handler(event)
      }
    }

    connect()

    return () => {
      manualCloseRef.current = true
      clearTimeout(retryTimeoutRef.current)
      wsRef.current?.close()
    }
  }, [addToast, closeCurrentMsg, endReport, failReport, onUnauthorized])

  // A question can go out: connected, no run, no reset and no report going (#417).
  const canSend = useCallback(() =>
    wsRef.current?.readyState === WebSocket.OPEN && !busyRef.current && !resettingRef.current && !reportingRef.current,
  [])

  // Returns whether the question went out, so the caller only clears what was typed when it did.
  const send = useCallback((content) => {
    if (!canSend()) return false
    busyRef.current = true
    setBusy(true)
    setThinking(true)
    const id = nextId()
    lastSentRef.current = { id, content, draft: true }
    setMessages(prev => [...prev, { id, role: 'user', content, done: true, model: modelRef.current }])
    wsRef.current.send(JSON.stringify({ action: 'message', content }))
    return true
  }, [canSend])

  const sendClarification = useCallback((choice) => {
    if (!canSend()) return
    busyRef.current = true
    setBusy(true)
    const id = nextId()
    lastSentRef.current = { id, content: choice, draft: false }
    setMessages(prev => [...prev, { id, role: 'user', content: choice, done: true, model: modelRef.current }])
    wsRef.current.send(JSON.stringify({ action: 'clarification_choice', choice }))
  }, [canSend])

  const sendSettings = useCallback((settings) => {
    if (settings.model) modelRef.current = settings.model
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'settings', settings }))
    } else {
      pendingSettingsRef.current = settings
    }
  }, [])

  const sendHistory = useCallback((msgs) => {
    const history = buildHistory(msgs)
    if (!history.length) return
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'history', messages: history }))
    } else {
      pendingHistoryRef.current = history
    }
  }, [])

  const stop = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ action: 'stop' }))
  }, [])

  const generateReport = useCallback((author) => {
    if (!wsRef.current || currentMsgRef.current) return
    reportingRef.current = true
    setReportBusy(true)
    setReportSpec(null)
    setReportProgress(NO_REPORT_PROGRESS)
    wsRef.current.send(JSON.stringify({ action: 'generate_report', author }))
    clearTimeout(reportTimeoutRef.current)
    reportTimeoutRef.current = setTimeout(() => {
      // Stop the server too: a report arriving after this message would contradict it.
      abandonReport()
      failReport(`Het rapport is na ${REPORT_TIMEOUT_MS / 60000} minuten nog niet klaar en is afgebroken. Probeer het opnieuw.`)
    }, REPORT_TIMEOUT_MS)
  }, [abandonReport, failReport])

  // The user stops the report (#339): no error, the button is free at once.
  const cancelReport = useCallback(() => {
    if (!reportingRef.current) return
    abandonReport()
    addToast('Rapport geannuleerd')
  }, [abandonReport, addToast])

  const clearRejectedDraft = useCallback(() => setRejectedDraft(null), [])

  const clearReport = useCallback(() => {
    endReport()
    setReportSpec(null)
  }, [endReport])

  const clear = useCallback(() => {
    setMessages([])
    // The ref too: send() checks it, and a stale true refused every next question (#337).
    busyRef.current = false
    setBusy(false)
    setThinking(false)
    currentMsgRef.current = null
    lastSentRef.current = null
  }, [])

  // "Nieuw gesprek": the server must forget the previous conversation too,
  // otherwise the next question is answered with its context (#70).
  const startNewConversation = useCallback(() => {
    clear()
    pendingHistoryRef.current = null
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      resettingRef.current = true
      setResetting(true)
      wsRef.current.send(JSON.stringify({ action: 'reset' }))
    }
  }, [clear])

  return { messages, busy, rejectedDraft, clearRejectedDraft, thinking, toasts, connected, resetting, reportBusy, reportProgress, reportSpec, send, sendClarification, sendSettings, sendHistory, stop, generateReport, cancelReport, clearReport, clear, startNewConversation, addToast }
}
