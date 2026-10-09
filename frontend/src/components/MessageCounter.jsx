// Characters typed against the message limit, from 80% of it (#481).
export default function MessageCounter({ count, max, atLimit, over }) {
  const className = ['message-counter', atLimit && 'message-counter--limit', over && 'message-counter--over']
    .filter(Boolean).join(' ')
  return (
    <span className={className} role="status" aria-live="polite">
      {count} / {max}<span className="sr-only"> tekens</span>
      {over && <> · te lang, kort je bericht in</>}
    </span>
  )
}
