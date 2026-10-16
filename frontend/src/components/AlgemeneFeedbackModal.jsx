/* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */
import { useId, useState } from 'react'
import { createPortal } from 'react-dom'
import { useDialog } from '../hooks/useDialog'
import { postAlgemeneFeedback } from '../api'

const SOORTEN = [['idee', 'Idee'], ['probleem', 'Probleem'], ['compliment', 'Compliment']]
const MAX_TEKST = 2000
// What the team gets (#600): the same pattern as the feedback per answer (AnswerFeedback).
const BEWAARD = 'Het team krijgt je bericht met je accountnaam en de pagina waar je was. ' +
  'Zet er geen persoonsgegevens in.'

// The route the user was on, as the server accepts it (core/algemene_feedback.PAGINA_PATROON): never a query
// or an ID, and anything else counts as the start page.
export function paginaVan(pathname) {
  return /^\/[a-z-]{0,30}$/.test(pathname) ? pathname : '/'
}

// A short general form (#600): an idea, a problem or a compliment, apart from an answer or a report. Rendered
// into <body> like the privacy popup: it can open from the settings dialog and must stack above it.
export default function AlgemeneFeedbackModal({ onClose }) {
  const dialogRef = useDialog(onClose)
  const titleId = useId()
  const bewaardId = useId()
  const [tekst, setTekst] = useState('')
  const [soort, setSoort] = useState(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const [verstuurd, setVerstuurd] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!tekst.trim() || sending) return
    setSending(true)
    setError(null)
    try {
      await postAlgemeneFeedback({ tekst: tekst.trim(), soort, pagina: paginaVan(window.location.pathname) })
      setVerstuurd(true)
    } catch (err) {
      setError(`Feedback niet verstuurd: ${err.message}`)
    } finally {
      setSending(false)
    }
  }

  const closeFromBackdrop = e => {
    // A portal's click still bubbles through the React tree to every host: stop it here.
    e.stopPropagation()
    onClose()
  }

  return createPortal(
    <div className="confirm-overlay algemene-feedback-overlay" onClick={closeFromBackdrop}>
      <form
        className="confirm-dialog feedback-dialog"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onSubmit={handleSubmit}
        onClick={e => e.stopPropagation()}
      >
        <h2 className="feedback-title" id={titleId}>Feedback over openEDUdata+</h2>
        {/* Always rendered: a live region inserted together with its text is often not announced. */}
        <p role="status" className="feedback-intro">{verstuurd ? 'Bedankt voor je feedback! Het team leest elk bericht.' : ''}</p>
        {verstuurd ? (
          <div className="confirm-actions">
            <button type="button" className="feedback-submit" onClick={onClose}>Sluiten</button>
          </div>
        ) : (
          <>
            <p className="feedback-intro">Een idee, iets dat niet werkt of een compliment: laat het ons weten.</p>
            <div className="feedback-question">
              <label htmlFor={`${titleId}-tekst`}>Wat wil je ons laten weten?</label>
              <textarea id={`${titleId}-tekst`} rows={4} maxLength={MAX_TEKST} value={tekst} aria-describedby={bewaardId}
                onChange={e => setTekst(e.target.value)} />
            </div>
            <fieldset className="feedback-question">
              <legend>Soort (optioneel)</legend>
              <div className="feedback-options choice">
                {SOORTEN.map(([waarde, label]) => (
                  <label key={waarde} className="feedback-option">
                    <input type="radio" name={`${titleId}-soort`} value={waarde} checked={soort === waarde}
                      onChange={() => setSoort(waarde)} />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <p className="feedback-intro" id={bewaardId}>{BEWAARD}</p>
            {error && <p role="alert" className="feedback-error">{error}</p>}
            <div className="confirm-actions">
              <button type="button" className="confirm-cancel" onClick={onClose}>Annuleren</button>
              <button type="submit" className="feedback-submit" disabled={!tekst.trim() || sending}>
                {sending ? 'Versturen…' : 'Versturen'}
              </button>
            </div>
          </>
        )}
      </form>
    </div>,
    document.body,
  )
}
