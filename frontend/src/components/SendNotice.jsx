import { useEffect } from 'react'

// How long the reason stays after a tap (#585).
export const SEND_NOTICE_MS = 4000

// Why a question cannot go out, above the composer (#585). The live region is always mounted, empty without a
// reason: a region mounted together with its text is often not announced (#532). `tap` is a new object for
// each refused tap, so a second tap starts the time again; onExpire ends the notice.
export default function SendNotice({ text, tap, onExpire }) {
  useEffect(() => {
    if (!tap) return
    const timer = setTimeout(onExpire, SEND_NOTICE_MS)
    return () => clearTimeout(timer)
  }, [tap, onExpire])
  return <p className="send-notice" role="status" aria-live="polite">{text}</p>
}
