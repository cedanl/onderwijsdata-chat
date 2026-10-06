import { useEffect, useId, useRef, useState } from 'react'

// Een getal dat de grondingscontrole doorstond, met de stap waar het vandaan komt (#365).
// Een knop, dus bereikbaar met het toetsenbord; Escape of buiten klikken sluit de uitleg.
// eslint-disable-next-line no-unused-vars -- node is react-markdown's AST node, not a DOM attribute
export default function CitedNumber({ node, children, ...props }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const id = useId()
  const label = props['data-label']

  useEffect(() => {
    if (!open) return undefined
    const sluit = e => {
      if (e.key === 'Escape' || (e.type === 'mousedown' && !ref.current?.contains(e.target))) setOpen(false)
    }
    document.addEventListener('keydown', sluit)
    document.addEventListener('mousedown', sluit)
    return () => {
      document.removeEventListener('keydown', sluit)
      document.removeEventListener('mousedown', sluit)
    }
  }, [open])

  if (!props['data-citatie']) return <span {...props}>{children}</span>
  return (
    <span className="citatie" ref={ref}>
      <button
        type="button"
        className="citatie-getal"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-label={`${children}, herkomst tonen`}
        onClick={() => setOpen(o => !o)}
      >
        {children}
      </button>
      {open && (
        <span id={id} role="note" className="citatie-uitleg">
          <strong>{label}</strong>
          {props['data-bron'] && <span>Bron: {props['data-bron']}</span>}
          {props['data-key'] && <span>Selectie: {props['data-key']}</span>}
        </span>
      )}
    </span>
  )
}
