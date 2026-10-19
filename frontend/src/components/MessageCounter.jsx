// The composer textarea points at the counter with aria-describedby; one composer per page.
export const MESSAGE_COUNTER_ID = 'message-counter'

// Characters typed against the message limit, shown from 80% of it (#481). The live region is always
// mounted, empty below 80%, so screen readers announce it when it fills. Over the limit a narrow screen
// shows only "te lang" next to the counter; the advice stays for screen readers (#612).
export default function MessageCounter({ count, max, atLimit, over, showCounter }) {
  const className = ['message-counter', atLimit && 'message-counter--limit', over && 'message-counter--over']
    .filter(Boolean).join(' ')
  return (
    <span id={MESSAGE_COUNTER_ID} className={className} role="status" aria-live="polite">
      {showCounter && <>{count} / {max}<span className="sr-only"> tekens</span></>}
      {over && <> · te lang<span className="message-counter-advies">, kort je bericht in</span></>}
    </span>
  )
}
