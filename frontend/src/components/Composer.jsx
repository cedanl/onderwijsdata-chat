import { useRef, useEffect, useLayoutEffect, useState, useCallback } from 'react'
import ChatInputFooter from './ChatInputFooter'
import SendNotice from './SendNotice'
import { MESSAGE_COUNTER_ID } from './MessageCounter'
import { messageLengthState } from '../messageLength'
import { MAX_TEXTAREA_HEIGHT } from '../constants'
import { persoonsgegevensMelding } from '../persoonsgegevens'
import { refusalReason, sendBlockReason } from '../sendBlockReason'

const NO_PREFILL = () => {}
const NO_MODELS = []

// Op een telefoon staat de privacyzin niet meer onder het veld (#596); de placeholder draagt hem, zonder
// hoogte te kosten. Hij staat weg zodra je typt, maar de waarschuwing bij een persoonsgegeven (#478) blijft.
export const PLACEHOLDER_COMPACT = 'Stel je vraag, zonder persoonsgegevens'
function placeholderTekst(hasMessages, compact) {
  if (compact) return PLACEHOLDER_COMPACT
  return hasMessages ? 'Stel een vervolgvraag...' : 'Bijv. hoeveel mbo-studenten zijn er in mijn regio?'
}
const REFUSED = 'refused'

// The reason a tap brought up (#585), only while it is still why sending is blocked. A refused question
// (send() said no) keeps a notice: the reason the chat gives by now, or a general one.
function noticeText(tap, reason, chat) {
  if (!tap) return ''
  if (tap.key === REFUSED) return refusalReason(chat).text
  return reason?.key === tap.key ? reason.text : ''
}

function autoResize(el) {
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT) + 'px'
}

// The draft lives here, not in ChatPage: a keystroke re-renders only the composer, not every message
// (and with it every markdown block and chart) above it.
//
// onSubmit(question) returns whether the question went out; only then is the draft cleared.
// connected, busy, resetting, reportBusy, atContextLimit: what decides, besides the draft, whether a question
// can go out; a tap while one blocks says why (#585).
// prefill ({ tekst }): a follow-up question the user picked (#364); it replaces the draft and is not sent.
// refusal ({}): a question sent from elsewhere ("Opnieuw") was refused; the notice here says why (#585).
export default function Composer({
  hasMessages, connected, busy, resetting = false, reportBusy = false, atContextLimit = false, models, selectedModel,
  onModelChange, onStop, onSubmit, max, rejectedDraft, clearRejectedDraft, prefill = null, clearPrefill = NO_PREFILL,
  refusal = null, clearRefusal = NO_PREFILL, compact = false,
}) {
  const [input, setInput] = useState('')
  // The refused tap: { key } of its reason, a new object per tap (SendNotice restarts its time on it).
  const [tap, setTap] = useState(null)
  const endNotice = useCallback(() => setTap(null), [])
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

  // "Opnieuw" under an error goes past the draft; when send() refuses it, the reason shows here too (#585).
  useEffect(() => {
    if (refusal === null) return
    setTap({ key: REFUSED })
    clearRefusal()
  }, [refusal, clearRefusal])

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
  const chat = { connected, busy, resetting, reporting: reportBusy, atContextLimit }
  const reason = sendBlockReason({ ...chat, text: input, over })
  const notice = noticeText(tap, reason, chat)

  // Its reason lapsed (typing, the connection back, the answer done): the notice is over, also when the reason
  // returns later. The text is already gone in this render; this only ends the tap.
  const lapsed = tap !== null && !notice
  useEffect(() => {
    if (lapsed) setTap(null)
  }, [lapsed])

  const handleSend = () => {
    // A blocked question, also one over the limit (#481), stays in the box; the notice says why.
    if (reason) {
      setTap({ key: reason.key })
      return
    }
    if (!onSubmit(input.trim())) {
      setTap({ key: REFUSED })
      return
    }
    setTap(null)
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
        placeholder={placeholderTekst(hasMessages, compact)}
        value={input}
        maxLength={2 * max}
        aria-describedby={MESSAGE_COUNTER_ID}
        onChange={e => { setInput(e.target.value); autoResize(e.target) }}
        onKeyDown={handleKey}
      />
      <SendNotice text={notice} tap={tap} onExpire={endNotice} />
      <ChatInputFooter
        connected={connected}
        busy={busy}
        models={compact ? NO_MODELS : models}
        selectedModel={selectedModel}
        onModelChange={onModelChange}
        onStop={onStop}
        onSend={handleSend}
        canSend={!reason}
        text={input}
        max={max}
      />
    </div>
  )
}
