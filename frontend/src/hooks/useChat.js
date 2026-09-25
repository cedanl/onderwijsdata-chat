import { useState, useEffect, useRef, useCallback } from 'react'
import { getToken, clearToken } from '../auth'
import { MAX_HISTORY } from '../constants'

const BACKOFF_DELAYS = [1000, 2000, 4000, 8000, 16000]
const MAX_RETRIES = 4

function buildHistory(messages) {
  return messages
    .filter(m =>
      (m.role === 'user' || m.role === 'assistant') &&
      m.content &&
      !m.isError &&
      !m.figures &&
      !m.clarification &&
      !m.starterQuestions
    )
    .map(({ role, content }) => ({ role, content }))
    .slice(-MAX_HISTORY)
}

function buildWsUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = getToken()
  const query = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${proto}://${location.host}/api/chat${query}`
}

export function useChat({ onUnauthorized } = {}) {
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [thinking, setThinking] = useState(false)
  const [toasts, setToasts] = useState([])
  const [connected, setConnected] = useState(false)
  const [reportBusy, setReportBusy] = useState(false)
  const [reportSpec, setReportSpec] = useState(null)
  const [resetting, setResetting] = useState(false)
  const wsRef = useRef(null)
  const currentMsgRef = useRef(null)
  const reportingRef = useRef(false)
  const pendingSettingsRef = useRef(null)
  const idRef = useRef(0)
  const manualCloseRef = useRef(false)
  const retryCountRef = useRef(0)
  const retryTimeoutRef = useRef(null)
  const pendingHistoryRef = useRef(null)
  const busyRef = useRef(false)
  const resettingRef = useRef(false)
  const nextId = () => ++idRef.current

  const addToast = useCallback((message, level = 'info') => {
    const id = nextId()
    setToasts(t => [...t, { id, message, level }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000)
  }, [])

  const cancelCurrentMsg = useCallback(() => {
    if (!currentMsgRef.current) return
    const id = currentMsgRef.current
    setMessages(prev => prev.filter(m => m.id !== id))
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
      message_start() {
        setThinking(false)
        const msgId = nextId()
        currentMsgRef.current = msgId
        setMessages(prev => [...prev, { id: msgId, role: 'assistant', content: '', tools: [], done: false }])
      },
      message_cancel() {
        cancelCurrentMsg()
      },
      text_delta(ev) {
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
          tools: m.tools.map(t =>
            t.name === ev.name ? { ...t, done: true, snippet: ev.snippet || null } : t
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
            // Numbers the server could not trace to this conversation's data (#185).
            ...(ev.unverified?.length && { unverified: ev.unverified }),
            // A finished turn without text would otherwise render nothing at all.
            ...(!content.trim() && !ev.aborted && { empty: true }),
          }
        })
        finishStream()
      },
      clarification(ev) {
        setThinking(false)
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
      report_ready(ev) {
        reportingRef.current = false
        setReportBusy(false)
        setReportSpec(ev.spec)
      },
      report_error(ev) {
        reportingRef.current = false
        setReportBusy(false)
        setReportSpec(null)
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant', content: ev.message, done: true, isError: true,
        }])
      },
      error(ev) {
        setThinking(false)
        cancelCurrentMsg()
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant', content: ev.message, done: true, isError: true,
        }])
        busyRef.current = false
        setBusy(false)
      },
    }

    const chatStreamEvents = new Set([
      'message_start', 'message_cancel', 'text_delta', 'tool_start',
      'tool_end', 'figure', 'message_end', 'clarification', 'starter_questions', 'error',
    ])

    function connect() {
      const ws = new WebSocket(buildWsUrl())
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        // A new connection is a new server session, so a pending reset is moot.
        resettingRef.current = false
        setResetting(false)
        retryCountRef.current = 0
        reportingRef.current = false
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
        if (reportingRef.current && chatStreamEvents.has(event.type)) return
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
  }, [addToast, cancelCurrentMsg, onUnauthorized])

  // Returns whether the question went out, so the caller only clears what was typed when it did.
  const send = useCallback((content) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN || busyRef.current || resettingRef.current) return false
    busyRef.current = true
    setBusy(true)
    setThinking(true)
    setMessages(prev => [...prev, { id: nextId(), role: 'user', content, done: true }])
    wsRef.current.send(JSON.stringify({ action: 'message', content }))
    return true
  }, [])

  const sendClarification = useCallback((choice) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN || busyRef.current || resettingRef.current) return
    busyRef.current = true
    setBusy(true)
    setMessages(prev => [...prev, { id: nextId(), role: 'user', content: choice, done: true }])
    wsRef.current.send(JSON.stringify({ action: 'clarification_choice', choice }))
  }, [])

  const sendSettings = useCallback((settings) => {
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
    wsRef.current.send(JSON.stringify({ action: 'generate_report', author }))
  }, [])

  const clearReport = useCallback(() => {
    reportingRef.current = false
    setReportBusy(false)
    setReportSpec(null)
  }, [])

  const clear = useCallback(() => {
    setMessages([])
    setBusy(false)
    currentMsgRef.current = null
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

  return { messages, busy, thinking, toasts, connected, resetting, reportBusy, reportSpec, send, sendClarification, sendSettings, sendHistory, stop, generateReport, clearReport, clear, startNewConversation, addToast }
}
