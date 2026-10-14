import { useRef, useEffect, useLayoutEffect, useState } from 'react'
import ChatInputFooter from './ChatInputFooter'
import { MESSAGE_COUNTER_ID } from './MessageCounter'
import { messageLengthState } from '../messageLength'
import { MAX_TEXTAREA_HEIGHT } from '../constants'
import { persoonsgegevensMelding } from '../persoonsgegevens'

const NO_PREFILL = () => {}

function autoResize(el) {
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT) + 'px'
}

// The draft lives here, not in ChatPage: a keystroke re-renders only the composer, not every message
// (and with it every markdown block and chart) above it.
//
// onSubmit(question) returns whether the question went out; only then is the draft cleared.
// ready: everything but the draft that lets a question go out (connected, idle, room left).
// prefill ({ tekst }): a follow-up question the user picked (#364); it replaces the draft and is not sent.
export default function Composer({
  hasMessages, connected, busy, ready, models, selectedModel, onModelChange, onStop, onSubmit,
  max, rejectedDraft, clearRejectedDraft, prefill = null, clearPrefill = NO_PREFILL,
}) {
  const [input, setInput] = useState('')
  // The prefill just applied: once the box holds its text, it gets the focus and its height.
  const [applied, setApplied] = useState(null)
  const textareaRef = useRef(null)

  // The server refused the question because a run was going: the typed text comes back (#145).
  useEffect(() => {
    if (rejectedDraft === null) return
    setInput(current => current || rejectedDraft)
    clearRejectedDraft()
  }, [rejectedDraft, clearRejectedDraft])

  // A picked follow-up question goes into the box for the user to edit or send (#364).
  useEffect(() => {
    if (prefill === null) return
    setInput(prefill.tekst)
    setApplied(prefill)
    clearPrefill()
  }, [prefill, clearPrefill])

  useLayoutEffect(() => {
    const el = textareaRef.current
    if (!applied || !el) return
    autoResize(el)
    el.focus()
    el.setSelectionRange(el.value.length, el.value.length)
  }, [applied])

  const over = messageLengthState(input, max).over
  // Waarschuwt, blokkeert niet (#478): een 9-cijferige code kan de elfproef toevallig doorstaan.
  const persoonsgegevens = persoonsgegevensMelding(input)

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
      {persoonsgegevens && (
        <p className="context-limit-banner context-limit-banner--warn" role="status" aria-live="polite">{persoonsgegevens}</p>
      )}
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
