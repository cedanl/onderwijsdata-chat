import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ConfirmModal from './components/ConfirmModal'

// Weggaan tijdens een antwoord of rapport stopt de run (#772): een andere pagina sluit de socket, een ander of nieuw
// gesprek stopt de taak op de server. Eerst een bevestiging dus. De app draait in een BrowserRouter, waarin useBlocker
// niet werkt; daarom gaan de eigen ingangen (navigatie, zoekpalet, gesprek openen, nieuw gesprek) door `bewaak`. De
// terugknop van de browser gaat er buiten om; ChatPage markeert de run dan bij het unmounten.
export const WEGGAAN_VRAAG = {
  antwoord: 'Er wordt nog een antwoord geschreven. Als je weggaat, stopt het; wat er al staat, blijft in het gesprek.',
  rapport: 'Er wordt nog een rapport gemaakt. Als je weggaat, stopt het en moet je het opnieuw maken.',
}

// Zonder provider (een pagina los getest) loopt elke actie meteen door.
const BewakingContext = createContext({ bewaak: actie => actie(), meld: () => {} })

export function RunBewaking({ children }) {
  // De lopende run: { soort: 'antwoord' | 'rapport', verlaat }, gezet door de pagina waar hij loopt.
  const lopendRef = useRef(null)
  const [vraag, setVraag] = useState(null)
  const [straks, setStraks] = useState(null)

  const bewaak = useCallback(actie => {
    const run = lopendRef.current
    if (run) setVraag({ soort: run.soort, actie })
    else actie()
  }, [])

  // Na bevestigen stopt de run eerst netjes; de actie volgt na de render die dat verwerkte. Dan heeft de pagina het
  // gestopte antwoord al in wat ze bewaart, en slaat een nieuw of ander gesprek dat op, niet het lopende.
  useEffect(() => {
    if (!straks) return
    setStraks(null)
    straks.actie()
  }, [straks])

  const bevestig = () => {
    lopendRef.current?.verlaat()
    setVraag(null)
    setStraks({ actie: vraag.actie })
  }

  const meld = useCallback(run => { lopendRef.current = run }, [])
  const waarde = useMemo(() => ({ bewaak, meld }), [bewaak, meld])
  return (
    <BewakingContext.Provider value={waarde}>
      {children}
      {vraag && (
        <ConfirmModal message={WEGGAAN_VRAAG[vraag.soort]} confirmLabel="Toch weggaan" cancelLabel="Blijven"
          onConfirm={bevestig} onCancel={() => setVraag(null)} />
      )}
    </BewakingContext.Provider>
  )
}

export function useBewaak() {
  return useContext(BewakingContext).bewaak
}

// Naar een andere pagina van de app, met de bevestiging als daar een run voor stopt. De pagina waar je al bent is geen
// weggaan.
export function useBewaakteNavigatie() {
  const bewaak = useBewaak()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  return useCallback(to => {
    if (new URL(to, window.location.origin).pathname === pathname) navigate(to)
    else bewaak(() => navigate(to))
  }, [bewaak, navigate, pathname])
}

// De pagina meldt haar lopende run (soort null: niets loopt). Tijdens de run vraagt de browser ook bij sluiten of
// herladen van het tabblad om bevestiging.
export function useLopendeRun(soort, verlaat) {
  const { meld } = useContext(BewakingContext)
  useEffect(() => {
    if (!soort) return
    meld({ soort, verlaat })
    const waarschuw = e => {
      e.preventDefault()
      e.returnValue = '' // oudere browsers vragen pas met returnValue
    }
    window.addEventListener('beforeunload', waarschuw)
    return () => {
      meld(null)
      window.removeEventListener('beforeunload', waarschuw)
    }
  }, [soort, verlaat, meld])
}
