import { useRef, useEffect, useState } from 'react'
import ChatInputFooter from './ChatInputFooter'
import { MESSAGE_COUNTER_ID } from './MessageCounter'
import { messageLengthState } from '../messageLength'
import { MAX_TEXTAREA_HEIGHT } from '../constants'

// The draft lives here, not in ChatPage: a keystroke re-renders only the composer, not every message
// (and with it every markdown block and chart) above it.
//
// onSubmit(question) returns whether the question went out; only then is the draft cleared.
// ready: everything but the draft that lets a question go out (connected, idle, room left).
export default function Composer({
  hasMessages, connected, busy, ready, models, selectedModel, onModelChange, onStop, onSubmit,
  max, rejectedDraft, clearRejectedDraft,
}) {
  const [input, setInput] = useState('')
  const textareaRef = useRef(null)

  // The server refused the question because a run was going: the typed text comes back (#145).
  useEffect(() => {
    if (rejectedDraft === null) return
    setInput(current => current || rejectedDraft)
    clearRejectedDraft()
  }, [rejectedDraft, clearRejectedDraft])

  const autoResize = (el) => {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT) + 'px'
  }

  const over = messageLengthState(input, max).over

  const handleSend = () => {
    const q = input.trim()
    // Over the limit (an older or restored draft) it stays in the box; the counter says why (#481).
    if (!q || over) return
    // A refused question stays in the box.
    if (!onSubmit(q)) return
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-input-wrap">
      <textarea
        ref={textareaRef}
        className="chat-input"
        aria-label="Chatbericht"
        rows={1}
        placeholder={hasMessages ? 'Stel een vervolgvraag...' : 'Bijv. hoeveel mbo-studenten zijn er in mijn regio?'}
        value={input}
        maxLength={2 * max}
        aria-describedby={MESSAGE_COUNTER_ID}
        onChange={e => { setInput(e.target.value); autoResize(e.target) }}
        onKeyDown={handleKey}
      />
      <ChatInputFooter
        connected={connected}
        busy={busy}
        models={models}
        selectedModel={selectedModel}
        onModelChange={onModelChange}
        onStop={onStop}
        onSend={handleSend}
        canSend={Boolean(input.trim()) && ready && !over}
        text={input}
        max={max}
      />
    </div>
  )
}
