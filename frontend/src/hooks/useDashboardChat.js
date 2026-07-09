import { useState, useRef, useEffect, useCallback } from 'react'
import { STORAGE_DC_MESSAGES, STORAGE_DC_FIGURES } from '../constants'
import { getToken } from '../auth'

const BACKOFF_DELAYS = [1000, 2000, 4000, 8000, 16000]
const MAX_RETRIES = 4

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
  const [generatingDashboard, setGeneratingDashboard] = useState(false)
  const [dashboardSpec, setDashboardSpec] = useState(null)
  const wsRef = useRef(null)
  const currentIdRef = useRef(null)
  const pendingSettingsRef = useRef(null)
  const idRef = useRef(0)
  const manualCloseRef = useRef(false)
  const retryCountRef = useRef(0)
  const retryTimeoutRef = useRef(null)
  const nextId = () => ++idRef.current

  useEffect(() => {
    try { localStorage.setItem(STORAGE_DC_MESSAGES, JSON.stringify(messages.filter(m => m.done))) } catch {}
  }, [messages])

  useEffect(() => {
    try { localStorage.setItem(STORAGE_DC_FIGURES, JSON.stringify(figures)) } catch {}
  }, [figures])

  useEffect(() => {
    manualCloseRef.current = false
    retryCountRef.current = 0

    function connect() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const token = getToken()
      const query = token ? `?token=${encodeURIComponent(token)}` : ''
      const ws = new WebSocket(`${proto}://${location.host}/api/chat${query}`)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        retryCountRef.current = 0
        if (pendingSettingsRef.current) {
          ws.send(JSON.stringify({ action: 'settings', settings: pendingSettingsRef.current }))
          pendingSettingsRef.current = null
        }
      }

      ws.onclose = () => {
        setConnected(false)
        setBusy(false)
        if (currentIdRef.current) {
          setMessages(prev => prev.map(m =>
            m.id === currentIdRef.current
              ? { ...m, done: true, tools: (m.tools || []).map(t => t.done ? t : { ...t, done: true }) }
              : m
          ))
          currentIdRef.current = null
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
        const ev = JSON.parse(e.data)
        if (ev.type === 'message_start') {
          const id = nextId()
          currentIdRef.current = id
          setMessages(prev => [...prev, { id, role: 'assistant', content: '', tools: [], done: false }])
        } else if (ev.type === 'message_cancel') {
          setMessages(prev => prev.filter(m => m.id !== currentIdRef.current))
          currentIdRef.current = null
        } else if (ev.type === 'text_delta') {
          setMessages(prev => prev.map(m =>
            m.id === currentIdRef.current ? { ...m, content: m.content + ev.content } : m
          ))
        } else if (ev.type === 'tool_start') {
          setMessages(prev => prev.map(m =>
            m.id === currentIdRef.current
              ? { ...m, tools: [...(m.tools || []), { name: ev.name, label: ev.label, done: false }] }
              : m
          ))
        } else if (ev.type === 'tool_end') {
          setMessages(prev => prev.map(m => {
            if (m.id !== currentIdRef.current) return m
            let matched = false
            return {
              ...m,
              tools: (m.tools || []).map(t => {
                if (!matched && t.name === ev.name && !t.done) {
                  matched = true
                  return { ...t, done: true, snippet: ev.snippet || null }
                }
                return t
              }),
            }
          }))
        } else if (ev.type === 'figure') {
          setFigures(prev => [...prev, ev.figure_json])
        } else if (ev.type === 'message_end') {
          setMessages(prev => prev.map(m =>
            m.id === currentIdRef.current ? { ...m, done: true } : m
          ))
          currentIdRef.current = null
          setBusy(false)
        } else if (ev.type === 'clarification') {
          setMessages(prev => [...prev, {
            id: nextId(), role: 'assistant',
            content: ev.vraag, clarification: ev.opties, done: true,
          }])
          currentIdRef.current = null
          setBusy(false)
        } else if (ev.type === 'dashboard_generating') {
          setGeneratingDashboard(true)
          setDashboardSpec(null)
        } else if (ev.type === 'dashboard_ready') {
          setGeneratingDashboard(false)
          setDashboardSpec(ev.spec)
        } else if (ev.type === 'error') {
          setGeneratingDashboard(false)
          setMessages(prev => [...prev, { id: nextId(), role: 'assistant', content: ev.message, done: true, isError: true }])
          setBusy(false)
        }
      }
    }

    connect()

    return () => {
      manualCloseRef.current = true
      clearTimeout(retryTimeoutRef.current)
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

  const refreshDashboard = useCallback((spec) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    wsRef.current.send(JSON.stringify({
      action: 'refresh_dashboard',
      recipe: spec.recipe,
      figure_recipes: spec.figure_recipes,
      spec,
    }))
  }, [])

  const reset = useCallback(() => {
    setMessages([])
    setFigures([])
    setBusy(false)
    setGeneratingDashboard(false)
    setDashboardSpec(null)
    try { localStorage.removeItem(STORAGE_DC_MESSAGES); localStorage.removeItem(STORAGE_DC_FIGURES) } catch {}
  }, [])

  return { messages, figures, busy, connected, send, sendClarification, sendSettings, reset, generateDashboard, refreshDashboard, generatingDashboard, dashboardSpec }
}
