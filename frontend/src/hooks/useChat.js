import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/chat`

export function useChat() {
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [toasts, setToasts] = useState([])
  const wsRef = useRef(null)
  const currentMsgRef = useRef(null)

  const addToast = useCallback((message, level = 'info') => {
    const id = Date.now()
    setToasts(t => [...t, { id, message, level }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000)
  }, [])

  useEffect(() => {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

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
        setMessages(prev => [...prev, {
          id: msgId,
          role: 'assistant',
          content: '',
          tools: [],
          done: false,
        }])
        return
      }

      if (event.type === 'text_delta') {
        setMessages(prev => prev.map(m =>
          m.id === currentMsgRef.current
            ? { ...m, content: m.content + event.content }
            : m
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
          m.id === currentMsgRef.current
            ? { ...m, done: true, actions: event.actions || [] }
            : m
        ))
        currentMsgRef.current = null
        setBusy(false)
        return
      }

      if (event.type === 'clarification') {
        const msgId = Date.now()
        setMessages(prev => [...prev, {
          id: msgId,
          role: 'assistant',
          content: event.vraag,
          clarification: event.opties,
          done: true,
        }])
        setBusy(false)
        return
      }

      if (event.type === 'starter_questions') {
        const msgId = Date.now()
        setMessages(prev => [...prev, {
          id: msgId,
          role: 'assistant',
          content: `Hier zijn voorbeeldvragen over **${event.label}**:`,
          starterQuestions: event.questions,
          done: true,
        }])
        setBusy(false)
        return
      }

      if (event.type === 'error') {
        setMessages(prev => [...prev, {
          id: Date.now(),
          role: 'assistant',
          content: event.message,
          done: true,
          isError: true,
        }])
        currentMsgRef.current = null
        setBusy(false)
        return
      }
    }

    ws.onclose = () => {
      setBusy(false)
    }

    return () => ws.close()
  }, [addToast])

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

  const stop = useCallback(() => {
    if (wsRef.current) wsRef.current.send(JSON.stringify({ action: 'stop' }))
  }, [])

  const clear = useCallback(() => {
    setMessages([])
    setBusy(false)
    currentMsgRef.current = null
  }, [])

  return { messages, busy, toasts, send, sendClarification, stop, clear }
}
