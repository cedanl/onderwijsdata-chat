import { useRef, useState } from 'react'
import ConversationExport from './ConversationExport'
import { NavSlot } from '../navSlot'
import { useEscape } from '../hooks/useEscape'

// De knoppen van de chat in de navbar op een telefoon (#596): de gesprekkenlijst en suggesties (de drawer),
// en een ⋯-menu voor wat niet bij elk bericht hoort, zoals het exporteren van het gesprek. Zo is er geen
// tweede balk onder de kop en geen vaste actierij boven het invoerveld.
// exportMessages: de berichten om te exporteren; null zolang er geen gesprek is (dan geen ⋯-menu).
export default function ChatNavActies({ sidebarOpen, onToggleSidebar, exportMessages }) {
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
              </div>
            </>
          )}
        </div>
      )}
    </NavSlot>
  )
}
