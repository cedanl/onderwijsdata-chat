import { useRef, useState } from 'react'
import ConversationExport from './ConversationExport'
import FeedbackLink from './FeedbackLink'
import PrivacyLink from './PrivacyLink'
import { NavSlot } from '../navSlot'
import { useEscape } from '../hooks/useEscape'

// De knoppen van de chat in de navbar op een telefoon (#596): de gesprekkenlijst en suggesties (de drawer),
// en een ⋯-menu voor wat niet bij elk bericht hoort, zoals het exporteren van het gesprek. Zo is er geen
// tweede balk onder de kop en geen vaste actierij boven het invoerveld.
// Sinds de disclaimer op een telefoon weg is (#596), staan de melding dat een vraag naar een externe AI-dienst
// gaat, de privacy-informatie en de feedbacklink hier ook (#608): één plek, twee tikken, zonder schermruimte.
// exportMessages: de berichten om te exporteren; null zolang er geen gesprek is (dan geen ⋯-menu, wel zijn plek).
// feedback: of het algemene feedbackformulier (#600) aanstaat.
export const EXTERNE_AI_MELDING = 'Je vraag gaat naar een externe AI-dienst en wordt bewaard. Voer geen persoonsgegevens in.'

export default function ChatNavActies({ sidebarOpen, onToggleSidebar, exportMessages, feedback = false }) {
  const [open, setOpen] = useState(false)
  const knopRef = useRef(null)
  useEscape(open, () => { setOpen(false); knopRef.current?.focus() })

  return (
    <NavSlot>
      <button
        type="button" className="navbar-icon-btn"
        aria-label="Gesprekken en suggesties" aria-expanded={sidebarOpen}
        onClick={onToggleSidebar}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="9" /><polyline points="12 7 12 12 15.5 14" />
        </svg>
      </button>
      {/* Zonder gesprek een lege plek ter breedte van de ⋯-knop (#649), geen knop en dus geen tabstop: anders schoof
          de gesprekkenknop bij het eerste bericht 44 px naar links. */}
      {!exportMessages && <span className="navbar-icon-slot" aria-hidden="true" />}
      {exportMessages && (
        <div className="navbar-meer">
          <button
            type="button" ref={knopRef} className="navbar-icon-btn"
            aria-label="Meer acties" aria-expanded={open} aria-controls="navbar-meer-menu"
            onClick={() => setOpen(o => !o)}
          >
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <circle cx="5" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="12" r="2" />
            </svg>
          </button>
          {open && (
            <>
              <div className="navbar-menu-overlay" onClick={() => setOpen(false)} aria-hidden="true" />
              <div className="navbar-meer-menu" id="navbar-meer-menu">
                <ConversationExport messages={exportMessages} onClose={() => setOpen(false)} />
                <div className="navbar-menu-scheiding" role="separator" />
                <p className="navbar-meer-noot">{EXTERNE_AI_MELDING}</p>
                <PrivacyLink className="navbar-menu-item">Privacy-informatie</PrivacyLink>
                {feedback && <FeedbackLink className="navbar-menu-item">Geef feedback</FeedbackLink>}
              </div>
            </>
          )}
        </div>
      )}
    </NavSlot>
  )
}
