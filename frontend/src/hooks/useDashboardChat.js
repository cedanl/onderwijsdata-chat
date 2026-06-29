import { useState, useRef, useEffect, useCallback } from 'react'
import { STORAGE_DC_MESSAGES, STORAGE_DC_FIGURES } from '../constants'
import { getToken } from '../auth'

const DC_MESSAGES_KEY = STORAGE_DC_MESSAGES
const DC_FIGURES_KEY = STORAGE_DC_FIGURES

function loadSessionMessages() {
  try { return JSON.parse(sessionStorage.getItem(DC_MESSAGES_KEY) || '[]') } catch { return [] }
}
function loadSessionFigures() {
  try { return JSON.parse(sessionStorage.getItem(DC_FIGURES_KEY) || '[]') } catch { return [] }
}

export default function useDashboardChat() {
  const [messages, setMessages] = useState(loadSessionMessages)
  const [figures, setFigures] = useState(loadSessionFigures)
  const [busy, setBusy] = useState(false)
  const wsRef = useRef(null)
  const currentIdRef = useRef(null)
  const pendingSettingsRef = useRef(null)
  const idRef = useRef(0)
  const nextId = () => ++idRef.current

  useEffect(() => {
    try { sessionStorage.setItem(DC_MESSAGES_KEY, JSON.stringify(messages.filter(m => m.done))) } catch {}
  }, [messages])

  useEffect(() => {
    try { sessionStorage.setItem(DC_FIGURES_KEY, JSON.stringify(figures)) } catch {}
  }, [figures])

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const token = getToken()
    const query = token ? `?token=${encodeURIComponent(token)}` : ''
    const ws = new WebSocket(`${proto}://${location.host}/api/chat${query}`)
    wsRef.current = ws

    ws.onopen = () => {
      if (pendingSettingsRef.current) {
        ws.send(JSON.stringify({ action: 'settings', settings: pendingSettingsRef.current }))
        pendingSettingsRef.current = null
      }
    }

    ws.onmessage = (e) => {
      const ev = JSON.parse(e.data)
      if (ev.type === 'message_start') {
        const id = nextId()
        currentIdRef.current = id
        setMessages(prev => [...prev, { id, role: 'assistant', content: '', done: false }])
      } else if (ev.type === 'message_cancel') {
        setMessages(prev => prev.filter(m => m.id !== currentIdRef.current))
        currentIdRef.current = null
      } else if (ev.type === 'text_delta') {
        setMessages(prev => prev.map(m =>
          m.id === currentIdRef.current ? { ...m, content: m.content + ev.content } : m
        ))
      } else if (ev.type === 'tool_start') {
        setMessages(prev => prev.map(m =>
          m.id === currentIdRef.current ? { ...m, toolLabel: ev.label } : m
        ))
      } else if (ev.type === 'tool_end') {
        setMessages(prev => prev.map(m =>
          m.id === currentIdRef.current ? { ...m, toolLabel: null } : m
        ))
      } else if (ev.type === 'figure') {
        setFigures(prev => [...prev, ev.figure_json])
      } else if (ev.type === 'message_end') {
        setMessages(prev => prev.map(m =>
          m.id === currentIdRef.current ? { ...m, done: true, toolLabel: null } : m
        ))
        currentIdRef.current = null
        setBusy(false)
      } else if (ev.type === 'clarification') {
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant',
          content: ev.vraag, clarification: ev.opties, done: true,
        }])
        setBusy(false)
      } else if (ev.type === 'error') {
        setMessages(prev => [...prev, { id: nextId(), role: 'assistant', content: ev.message, done: true, isError: true }])
        setBusy(false)
      }
    }
    ws.onclose = () => setBusy(false)
    return () => ws.close()
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

  const reset = useCallback(() => {
    setMessages([])
    setFigures([])
    setBusy(false)
    try { sessionStorage.removeItem(DC_MESSAGES_KEY); sessionStorage.removeItem(DC_FIGURES_KEY) } catch {}
  }, [])

  return { messages, figures, busy, send, sendClarification, sendSettings, reset }
}
