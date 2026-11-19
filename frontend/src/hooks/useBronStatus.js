import { useEffect, useState } from 'react'

// Hoe vaak de lijst opnieuw wordt opgehaald (#1057). De server meet de bronnen zelf elke twee minuten; vaker vragen
// levert geen nieuwer antwoord. Een melding verdwijnt zo binnen enkele minuten nadat een bron weer antwoordt.
export const VERVERS_MS = 120_000

// De bronnen die nu niet live zijn, volgens /api/bronstatus (openbaar, geen inlog). Eén keer bij het openen, daarna
// elke VERVERS_MS, zodra het netwerk terugkomt en zodra de pagina weer zichtbaar wordt: zo ziet een tab die lang
// op de achtergrond stond ook de stand van nu. Zonder antwoord blijft de laatst bekende lijst staan; de eerste keer is
// dat een lege lijst, dus er komt nooit een melding uit onzekerheid.
export function useBronStatus() {
  const [nietLive, setNietLive] = useState([])
  useEffect(() => {
    let gestopt = false
    const haalOp = () => {
      fetch('/api/bronstatus')
        .then(r => (r.ok ? r.json() : null))
        .then(data => {
          if (!gestopt && data && Array.isArray(data.niet_live)) setNietLive(data.niet_live)
        })
        .catch(() => {})
    }
    const bijZichtbaar = () => {
      if (document.visibilityState !== 'hidden') haalOp()
    }
    haalOp()
    const timer = setInterval(haalOp, VERVERS_MS)
    window.addEventListener('online', haalOp)
    document.addEventListener('visibilitychange', bijZichtbaar)
    return () => {
      gestopt = true
      clearInterval(timer)
      window.removeEventListener('online', haalOp)
      document.removeEventListener('visibilitychange', bijZichtbaar)
    }
  }, [])
  return nietLive
}
