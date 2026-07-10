import { useState, useEffect, useRef, useCallback } from 'react'
import { getToken, clearToken } from '../auth'

const BACKOFF_DELAYS = [1000, 2000, 4000, 8000, 16000]
const MAX_RETRIES = 4

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
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const currentMsgRef = useRef(null)
  const pendingSettingsRef = useRef(null)
  const idRef = useRef(0)
  const manualCloseRef = useRef(false)
  const retryCountRef = useRef(0)
  const retryTimeoutRef = useRef(null)
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

    function updateCurrentMsg(updater) {
      setMessages(prev => prev.map(m =>
        m.id === currentMsgRef.current ? updater(m) : m
      ))
    }

    function finishStream() {
      currentMsgRef.current = null
      setBusy(false)
    }

    const messageHandlers = {
      system_message(ev) {
        addToast(ev.message, 'warning')
      },
      toast(ev) {
        addToast(ev.message, ev.level || 'info')
      },
      message_start() {
        const msgId = nextId()
        currentMsgRef.current = msgId
        setMessages(prev => [...prev, { id: msgId, role: 'assistant', content: '', tools: [], done: false }])
      },
      message_cancel() {
        cancelCurrentMsg()
      },
      text_delta(ev) {
        updateCurrentMsg(m => ({ ...m, content: m.content + ev.content }))
      },
      tool_start(ev) {
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
      starter_questions(ev) {
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant',
          content: `Hier zijn voorbeeldvragen over **${ev.label}**:`,
          starterQuestions: ev.questions, done: true,
        }])
        finishStream()
      },
      error(ev) {
        cancelCurrentMsg()
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant', content: ev.message, done: true, isError: true,
        }])
        setBusy(false)
      },
    }

    function connect() {
      const ws = new WebSocket(buildWsUrl())
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        retryCountRef.current = 0
        if (pendingSettingsRef.current) {
          ws.send(JSON.stringify({ action: 'settings', settings: pendingSettingsRef.current }))
          pendingSettingsRef.current = null
        }
      }

      ws.onclose = (e) => {
        setConnected(false)
        setBusy(false)

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

  return { messages, busy, toasts, connected, send, sendClarification, sendSettings, stop, clear }
}
