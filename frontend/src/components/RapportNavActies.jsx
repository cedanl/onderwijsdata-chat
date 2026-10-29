import { useRef, useState } from 'react'
import WorkbookDownload from './WorkbookDownload'
import { NavSlot } from '../navSlot'
import { useEscape } from '../hooks/useEscape'
import { rapportWoord } from '../rapportWoord'

// De knoppen van een geopend rapport in de navbar op een telefoon (#604): downloaden en feedback passen
// niet naast een titel van twee regels, dus staan ze — net als bij de chat (#596, ChatNavActies) — in een
// ⋯-menu in de nav-slot. Desktop toont ze inline in de kopbalk (WorkbookViewer).
// afdrukken: de knop "Opslaan als PDF" (#622), als menu-item; null voor een rapport dat het niet kan.
export default function RapportNavActies({ workbook, instelling, save, feedbackEnabled, feedbackGiven, onFeedback, afdrukken = null }) {
  const [open, setOpen] = useState(false)
  const knopRef = useRef(null)
  useEscape(open, () => { setOpen(false); knopRef.current?.focus() })

  return (
    <NavSlot>
      <div className="navbar-meer">
        <button
          type="button" ref={knopRef} className="navbar-icon-btn"
          aria-label="Meer acties" aria-expanded={open} aria-controls="navbar-meer-rapport"
          onClick={() => setOpen(o => !o)}
        >
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <circle cx="5" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="12" r="2" />
          </svg>
        </button>
        {open && (
          <>
            <div className="navbar-menu-overlay" onClick={() => setOpen(false)} aria-hidden="true" />
            <div className="navbar-meer-menu" id="navbar-meer-rapport">
              <WorkbookDownload workbook={workbook} instelling={instelling} save={save} />
              {afdrukken}
              {feedbackEnabled && (feedbackGiven ? (
                <span className="navbar-menu-item" role="status">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  Feedback gegeven
                </span>
              ) : (
                <button type="button" className="navbar-menu-item" onClick={() => { setOpen(false); onFeedback() }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                  Geef feedback op dit {rapportWoord(workbook)}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </NavSlot>
  )
}
