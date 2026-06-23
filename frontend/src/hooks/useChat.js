import { useState, useEffect, useRef, useCallback } from 'react'
import { getToken, clearToken } from '../auth'

function buildWsUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = getToken()
  const query = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${proto}://${location.host}/api/chat${query}`
}

export function useChat({ onUnauthorized } = {}) {
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [toasts, setToasts] = useState([])
  const wsRef = useRef(null)
  const currentMsgRef = useRef(null)
  const pendingSettingsRef = useRef(null)

  const addToast = useCallback((message, level = 'info') => {
    const id = Date.now()
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
    const ws = new WebSocket(buildWsUrl())
    wsRef.current = ws

    ws.onopen = () => {
      if (pendingSettingsRef.current) {
        ws.send(JSON.stringify({ action: 'settings', settings: pendingSettingsRef.current }))
        pendingSettingsRef.current = null
      }
    }

    ws.onclose = (e) => {
      setBusy(false)
      if (e.code === 4001) {
        clearToken()
        onUnauthorized?.()
      }
    }

    ws.onmessage = (e) => {
      const event = JSON.parse(e.data)

      if (event.type === 'system_message') {
        addToast(event.message, 'warning')
        return
      }
      if (event.type === 'toast') {
        addToast(event.message, event.level || 'info')
        return
      }
      if (event.type === 'message_start') {
        const msgId = Date.now()
        currentMsgRef.current = msgId
        setMessages(prev => [...prev, { id: msgId, role: 'assistant', content: '', tools: [], done: false }])
        return
      }
      if (event.type === 'message_cancel') {
        cancelCurrentMsg()
        return
      }
      if (event.type === 'text_delta') {
        setMessages(prev => prev.map(m =>
          m.id === currentMsgRef.current ? { ...m, content: m.content + event.content } : m
        ))
        return
      }
      if (event.type === 'tool_start') {
        setMessages(prev => prev.map(m =>
          m.id === currentMsgRef.current
            ? { ...m, tools: [...m.tools, { name: event.name, label: event.label, done: false }] }
            : m
        ))
        return
      }
      if (event.type === 'tool_end') {
        setMessages(prev => prev.map(m =>
          m.id === currentMsgRef.current
            ? { ...m, tools: m.tools.map(t => t.name === event.name ? { ...t, done: true } : t) }
            : m
        ))
        return
      }
      if (event.type === 'message_end') {
        setMessages(prev => prev.map(m =>
          m.id === currentMsgRef.current ? { ...m, done: true } : m
        ))
        currentMsgRef.current = null
        setBusy(false)
        return
      }
      if (event.type === 'clarification') {
        setMessages(prev => [...prev, {
          id: Date.now(), role: 'assistant',
          content: event.vraag, clarification: event.opties, done: true,
        }])
        currentMsgRef.current = null
        setBusy(false)
        return
      }
      if (event.type === 'starter_questions') {
        setMessages(prev => [...prev, {
          id: Date.now(), role: 'assistant',
          content: `Hier zijn voorbeeldvragen over **${event.label}**:`,
          starterQuestions: event.questions, done: true,
        }])
        currentMsgRef.current = null
        setBusy(false)
        return
      }
      if (event.type === 'error') {
        cancelCurrentMsg()
        setMessages(prev => [...prev, {
          id: Date.now(), role: 'assistant', content: event.message, done: true, isError: true,
        }])
        setBusy(false)
        return
      }
    }

    return () => ws.close()
  }, [addToast, cancelCurrentMsg, onUnauthorized])

  const send = useCallback((content) => {
    if (!wsRef.current || busy) return
    setBusy(true)
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content, done: true }])
    wsRef.current.send(JSON.stringify({ action: 'message', content }))
  }, [busy])

  const sendClarification = useCallback((choice) => {
    if (!wsRef.current || busy) return
    setBusy(true)
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: choice, done: true }])
    wsRef.current.send(JSON.stringify({ action: 'clarification_choice', choice }))
  }, [busy])

  const sendSettings = useCallback((settings) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'settings', settings }))
    } else {
      pendingSettingsRef.current = settings
    }
  }, [])

  const stop = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ action: 'stop' }))
  }, [])

  const clear = useCallback(() => {
    setMessages([])
    setBusy(false)
    currentMsgRef.current = null
  }, [])

  return { messages, busy, toasts, send, sendClarification, sendSettings, stop, clear }
}
