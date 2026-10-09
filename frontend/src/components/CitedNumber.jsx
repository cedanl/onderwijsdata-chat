import { useEffect, useId, useRef, useState } from 'react'

// Een getal uit een dataantwoord met zijn herkomst (#365, #415): eerst bron en selectie in
// woorden, dan maat en stap, de technische key dichtgeklapt onder "Technische details" (CH-30r).
// Zonder vastgestelde herkomst zegt de uitleg dat. Een knop, dus bereikbaar met het toetsenbord;
// Escape of buiten klikken sluit, en Escape zet de focus terug op de knop.
// eslint-disable-next-line no-unused-vars -- node is react-markdown's AST node, not a DOM attribute
export default function CitedNumber({ node, children, ...props }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const knop = useRef(null)
  const id = useId()
  const onbepaald = props['data-onbepaald'] !== undefined

  useEffect(() => {
    if (!open) return undefined
    const sluit = e => {
      if (e.key === 'Escape') {
        // De summary in de uitleg kan focus hebben; zonder dit viel de focus na sluiten op <body>.
        if (ref.current?.contains(document.activeElement)) knop.current?.focus()
        setOpen(false)
      } else if (e.type === 'mousedown' && !ref.current?.contains(e.target)) setOpen(false)
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
        ref={knop}
        type="button"
        className={onbepaald ? 'citatie-getal citatie-onbepaald' : 'citatie-getal'}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-label={`${children}, herkomst tonen`}
        onClick={() => setOpen(o => !o)}
      >
        {children}
      </button>
      {open && (
        <span id={id} role="note" className="citatie-uitleg">
          {onbepaald ? <Onbepaald reden={props['data-onbepaald']} /> : <Herkomst {...props} />}
        </span>
      )}
    </span>
  )
}

// Waarom de herkomst niet vaststaat (agent/citaties.py, CH-38): het getal staat er niet als
// meetwaarde in, of het staat er meer dan eens in en de zin wijst geen van die plekken aan.
function Onbepaald({ reden }) {
  return (
    <>
      <strong>Herkomst niet vastgesteld</strong>
      <span>
        {reden === 'meerdere'
          ? 'Dit getal staat meer dan eens in de opgehaalde data; de zin wijst niet aan welke het is.'
          : 'Dit getal staat niet als meetwaarde in de opgehaalde data.'}
      </span>
    </>
  )
}

function Herkomst(props) {
  const stap = props['data-stap']
  const label = props['data-label']
  return (
    <>
      <strong>{props['data-bron'] || label}</strong>
      {props['data-selectie'] && <span>{props['data-selectie']}</span>}
      {props['data-maat'] && <span>{props['data-maat']}</span>}
      {stap && <span className="citatie-stap">Stap {stap}: {label}</span>}
      {props['data-key'] && (
        // CH-30r: de key is het enige spoor van getal naar toolstap en store, maar jargon in de leesregel.
        <details className="citatie-details">
          <summary>Technische details</summary>
          <code className="citatie-key">{props['data-key']}</code>
        </details>
      )}
    </>
  )
}
