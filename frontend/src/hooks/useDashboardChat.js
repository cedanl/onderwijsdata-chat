import { useState, useRef, useEffect, useCallback } from 'react'
import { STORAGE_DC_MESSAGES, STORAGE_DC_FIGURES } from '../constants'
import { chatSocket, checkSession, getToken, sessionEndedSince } from '../auth'
import { finishStep } from '../toolSteps'
import { createHeartbeat, createRetry, opgevenBij, watchNetwork } from '../socketHealth'

function loadSessionMessages() {
  try { return JSON.parse(localStorage.getItem(STORAGE_DC_MESSAGES) || '[]') } catch { return [] }
}
function loadSessionFigures() {
  try { return JSON.parse(localStorage.getItem(STORAGE_DC_FIGURES) || '[]') } catch { return [] }
}

export default function useDashboardChat() {
  const [messages, setMessages] = useState(loadSessionMessages)
  const [figures, setFigures] = useState(loadSessionFigures)
  const [busy, setBusy] = useState(false)
  const [connected, setConnected] = useState(false)
  // Zoals in de chat (#783): geen eigen pogingen meer, en waarom.
  const [opgegeven, setOpgegeven] = useState(null)
  const verbindOpnieuwRef = useRef(() => {})
  const [generatingDashboard, setGeneratingDashboard] = useState(false)
  const [dashboardSpec, setDashboardSpec] = useState(null)
  const wsRef = useRef(null)
  const currentIdRef = useRef(null)
  const pendingSettingsRef = useRef(null)
  const idRef = useRef(0)
  const manualCloseRef = useRef(false)
  const nextId = () => ++idRef.current
  // Logout and session end clear the token before they wipe this chat from storage. A save
  // React runs after that (still pending from the last streamed token) must not write the
  // previous user's chat back (#498).
  const [tokenAtMount] = useState(getToken)

  useEffect(() => {
    if (sessionEndedSince(tokenAtMount)) return
    try { localStorage.setItem(STORAGE_DC_MESSAGES, JSON.stringify(messages.filter(m => m.done))) } catch { /* noop */ }
  }, [messages, tokenAtMount])

  useEffect(() => {
    if (sessionEndedSince(tokenAtMount)) return
    try { localStorage.setItem(STORAGE_DC_FIGURES, JSON.stringify(figures)) } catch { /* noop */ }
  }, [figures, tokenAtMount])

  useEffect(() => {
    manualCloseRef.current = false

    function updateCurrentMsg(updater) {
      setMessages(prev => prev.map(m =>
        m.id === currentIdRef.current ? updater(m) : m
      ))
    }

    function finishStream() {
      currentIdRef.current = null
      setBusy(false)
    }

    const messageHandlers = {
      message_start() {
        const id = nextId()
        currentIdRef.current = id
        setMessages(prev => [...prev, { id, role: 'assistant', content: '', tools: [], done: false }])
      },
      message_cancel() {
        setMessages(prev => prev.filter(m => m.id !== currentIdRef.current))
        currentIdRef.current = null
      },
      text_delta(ev) {
        updateCurrentMsg(m => ({ ...m, content: m.content + ev.content }))
      },
      tool_start(ev) {
        updateCurrentMsg(m => ({
          ...m, tools: [...(m.tools || []), { name: ev.name, label: ev.label, done: false }],
        }))
      },
      tool_end(ev) {
        updateCurrentMsg(m => {
          let matched = false
          return {
            ...m,
            tools: (m.tools || []).map(t => {
              if (!matched && t.name === ev.name && !t.done) {
                matched = true
                return finishStep(t, ev)
              }
              return t
            }),
          }
        })
      },
      figure(ev) {
        setFigures(prev => [...prev, ev.figure_json])
      },
      message_end() {
        updateCurrentMsg(m => ({ ...m, done: true }))
        finishStream()
      },
      clarification(ev) {
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant',
          content: ev.vraag, clarification: ev.opties, done: true,
        }])
        finishStream()
      },
      dashboard_generating() {
        setGeneratingDashboard(true)
        setDashboardSpec(null)
      },
      dashboard_ready(ev) {
        setGeneratingDashboard(false)
        setDashboardSpec(ev.spec)
      },
      error(ev) {
        setGeneratingDashboard(false)
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant', content: ev.message, done: true, isError: true,
        }])
        setBusy(false)
      },
    }

    // Same gap as the chat (#489): a silently dead connection fires onclose only
    // after the TCP timeout, so the melding never came.
    const heartbeat = createHeartbeat(() => wsRef.current, connectionLost)
    const retry = createRetry(connect, { opgegeven: () => setOpgegeven('weg') })

    // One live socket at a time, as in the chat (#522): a replaced socket is inert, and the
    // loss of the current one is handled once, whichever signal comes first.
    let opened = false
    let ended = false
    const isCurrent = (ws) => wsRef.current === ws && !ended

    // The open answer ends where it was: its running steps count as done.
    function endOpenMessage() {
      const id = currentIdRef.current
      if (!id) return
      setMessages(prev => prev.map(m =>
        m.id === id
          ? { ...m, done: true, tools: (m.tools || []).map(t => t.done ? t : { ...t, done: true }) }
          : m
      ))
      currentIdRef.current = null
    }

    function connectionLost(ws, code) {
      if (!isCurrent(ws)) return
      ended = true
      heartbeat.stop()
      setConnected(false)
      setBusy(false)
      endOpenMessage()

      if (manualCloseRef.current) return
      const reden = opgevenBij(code)
      if (reden) {
        retry.reset()
        setOpgegeven(reden)
        return
      }
      // A refused handshake (expired token) closes as a bare 1006 before opening (#480).
      if (!opened) checkSession()
      retry.schedule()
    }

    function connect() {
      const ws = chatSocket()
      wsRef.current = ws
      opened = false
      ended = false
      setOpgegeven(null)

      ws.onopen = () => {
        if (!isCurrent(ws)) return
        opened = true
        setConnected(true)
        heartbeat.start()
        retry.opened()
        if (pendingSettingsRef.current) {
          ws.send(JSON.stringify({ action: 'settings', settings: pendingSettingsRef.current }))
          pendingSettingsRef.current = null
        }
      }

      ws.onclose = (e) => connectionLost(ws, e.code)

      ws.onmessage = (e) => {
        if (!isCurrent(ws)) return
        heartbeat.alive()
        const ev = JSON.parse(e.data)
        const handler = messageHandlers[ev.type]
        if (handler) handler(ev)
      }
    }

    connect()

    const detachNetwork = watchNetwork({ getWs: () => wsRef.current, lost: connectionLost, retry, connect })

    verbindOpnieuwRef.current = () => {
      const state = wsRef.current?.readyState
      if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) return
      retry.reset()
      connect()
    }

    return () => {
      manualCloseRef.current = true
      detachNetwork()
      heartbeat.stop()
      retry.reset()
      wsRef.current?.close()
    }
  }, [])

  const send = useCallback((content) => {
    if (!wsRef.current || busy) return
    setBusy(true)
    setMessages(prev => [...prev, { id: nextId(), role: 'user', content, done: true }])
    wsRef.current.send(JSON.stringify({ action: 'message', content }))
  }, [busy])

  const sendClarification = useCallback((choice) => {
    if (!wsRef.current || busy) return
    setBusy(true)
    setMessages(prev => [...prev, { id: nextId(), role: 'user', content: choice, done: true }])
    wsRef.current.send(JSON.stringify({ action: 'clarification_choice', choice }))
  }, [busy])

  const sendSettings = useCallback((settings) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      pendingSettingsRef.current = settings
      return
    }
    wsRef.current.send(JSON.stringify({ action: 'settings', settings }))
  }, [])

  const generateDashboard = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    wsRef.current.send(JSON.stringify({ action: 'generate_dashboard' }))
  }, [])

  const refreshDashboard = useCallback((spec, mode = 'ververs') => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    wsRef.current.send(JSON.stringify({
      action: 'refresh_dashboard',
      recipe: spec.recipe,
      figure_recipes: spec.figure_recipes,
      spec,
      mode,
    }))
  }, [])

  const reset = useCallback(() => {
    setMessages([])
    setFigures([])
    setBusy(false)
    setGeneratingDashboard(false)
    setDashboardSpec(null)
    try { localStorage.removeItem(STORAGE_DC_MESSAGES); localStorage.removeItem(STORAGE_DC_FIGURES) } catch { /* noop */ }
  }, [])

  const verbindOpnieuw = useCallback(() => verbindOpnieuwRef.current(), [])

  return { messages, figures, busy, connected, opgegeven, verbindOpnieuw, send, sendClarification, sendSettings, reset, generateDashboard, refreshDashboard, generatingDashboard, dashboardSpec }
}
