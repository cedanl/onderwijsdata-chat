import { useEffect, useRef, useState } from 'react'

const RESET_MS = 1500
const ANNOUNCEMENTS = { copied: 'Gekopieerd', failed: 'Kopiëren mislukt' }

// navigator.clipboard exists only in secure contexts; its absence counts as a failed copy.
async function writeClipboard(text) {
  if (!navigator.clipboard) throw new Error('Clipboard unavailable')
  await navigator.clipboard.writeText(text)
}

// Copies `text` and confirms it next to the button for a moment (#492). The visible
// "Gekopieerd" is aria-hidden: the always-rendered live region is the only announcer.
export default function CopyButton({ text, className }) {
  const [status, setStatus] = useState(null)
  const timer = useRef(null)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      clearTimeout(timer.current)
    }
  }, [])

  function show(next) {
    if (!mounted.current) return
    clearTimeout(timer.current)
    setStatus(next)
    timer.current = setTimeout(() => setStatus(null), RESET_MS)
  }

  const handleCopy = () => {
    writeClipboard(text).then(() => show('copied'), () => show('failed'))
  }

  const copied = status === 'copied'
  return (
    <>
      <button type="button" className={`copy-btn ${className || ''}`} onClick={handleCopy} title="Kopieer"
        aria-label="Kopieer" data-copied={copied || undefined}>
        {copied ? (
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
        )}
        {copied && <span aria-hidden="true">{ANNOUNCEMENTS.copied}</span>}
      </button>
      <span className="sr-only" role="status" aria-live="polite">{status ? ANNOUNCEMENTS[status] : ''}</span>
    </>
  )
}
