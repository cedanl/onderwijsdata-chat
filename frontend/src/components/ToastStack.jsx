import { useEffect, useRef } from 'react'

// De meldingen van de chat. Een melding met een knop (Ongedaan maken, #493) kan meer (#776):
// - `pauzeer`/`hervat`: de tijd staat stil zolang de muis erop staat of het toetsenbord erin zit;
// - `focus`: de knop krijgt bij het verschijnen de focus;
// - `verlaat`: Tab of Escape op de knop, of de melding die verdwijnt terwijl de focus erin staat, zet de
//   focus terug op een plek in de pagina (het volgende gesprek in de lijst).
export default function ToastStack({ toasts }) {
  return (
    <div className="toast-stack">
      {toasts.map(t => <Toast key={t.id} toast={t} />)}
    </div>
  )
}

// Focus na een muisklik telt niet als "het toetsenbord zit erin": anders stond de tijd stil tot de
// gebruiker ergens anders klikte, en ging de verwijdering niet door. Kent de browser :focus-visible
// niet, dan telt elke focus.
function toetsenbordFocus(el) {
  try {
    return el.matches(':focus-visible')
  } catch {
    return true
  }
}

function Toast({ toast: t }) {
  const knopRef = useRef(null)
  const hover = useRef(false)
  const toetsenbord = useRef(false)
  const focusBinnen = useRef(false)
  const stil = useRef(false)
  const toastRef = useRef(t)
  toastRef.current = t

  function bijwerken() {
    const nu = hover.current || toetsenbord.current
    if (nu === stil.current) return
    stil.current = nu
    ;(nu ? toastRef.current.pauzeer : toastRef.current.hervat)?.()
  }

  useEffect(() => {
    if (toastRef.current.focus) knopRef.current?.focus()
    // Weg terwijl de focus erin stond (de tijd om, of Ongedaan maken geklikt): niet op <body> laten vallen.
    return () => { if (focusBinnen.current) toastRef.current.verlaat?.() }
  }, [])

  const verlaatMetToets = e => {
    if (!t.verlaat || (e.key !== 'Tab' && e.key !== 'Escape')) return
    e.preventDefault()
    t.verlaat()
  }

  return (
    <div
      className={`toast ${t.level}`}
      role="status"
      onMouseEnter={() => { hover.current = true; bijwerken() }}
      onMouseLeave={() => { hover.current = false; bijwerken() }}
      onFocus={e => { focusBinnen.current = true; toetsenbord.current = toetsenbordFocus(e.target); bijwerken() }}
      onBlur={e => {
        if (e.currentTarget.contains(e.relatedTarget)) return
        focusBinnen.current = false
        toetsenbord.current = false
        bijwerken()
      }}
    >
      {t.message}
      {t.actie && (
        <button ref={knopRef} type="button" className="toast-actie" onClick={t.actie.onClick} onKeyDown={verlaatMetToets}>
          {t.actie.label}
        </button>
      )}
    </div>
  )
}
