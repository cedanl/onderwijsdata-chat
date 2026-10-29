import { useEffect, useId, useRef, useState } from 'react'
import { scrollGedrag } from '../hooks/useMediaQuery'

// Same text and duration as the report feedback toast (WorkbookViewer).
const THANKS = 'Bedankt voor je feedback!'
const THANKS_MS = 4000
// What every judgement keeps, 👍 and 👎 (#476): the trace goes to the team and stays when the conversation is
// deleted, without the user's name, until 90 days after it was given (#485, persistence/opschonen.py).
const BEWAARD = 'Het team krijgt je oordeel met de vraag, het antwoord en de stappen erbij. ' +
  'Verwijder je het gesprek, dan blijft dit bewaard, maar zonder je naam. Na 90 dagen wordt het verwijderd.'
// A thumbs-up shows no dialog, so its thanks carries BEWAARD (#807): 36 words, readable in 15 s also at
// 150 words a minute. A thumbs-down keeps THANKS_MS: its dialog showed the sentence before Verstuur.
const BEWAARD_MS = 15000

// 👍/👎 under an answer (#248). A thumbs-down asks what is wrong first: with the
// trace the server adds, that makes it a reproducible bug report.
export default function AnswerFeedback({ value, onSubmit }) {
  const [explaining, setExplaining] = useState(false)
  const [toelichting, setToelichting] = useState('')
  const [error, setError] = useState(null)
  // Counts successful submits, 0 = no confirmation; a new submit restarts the timeout.
  const [thanks, setThanks] = useState(0)
  // Whether the confirmation also says what is kept: only after a thumbs-up.
  const [metBewaard, setMetBewaard] = useState(false)
  const fieldRef = useRef(null)
  const statusRef = useRef(null)
  const bewaardId = useId()
  const toontBewaard = thanks > 0 && metBewaard

  useEffect(() => {
    if (explaining) fieldRef.current?.focus()
  }, [explaining])

  useEffect(() => {
    if (!thanks) return
    const timer = setTimeout(() => setThanks(0), metBewaard ? BEWAARD_MS : THANKS_MS)
    return () => clearTimeout(timer)
  }, [thanks, metBewaard])

  // Under the last answer on a phone the sentence would fall below the edge of the list: scroll just that far.
  useEffect(() => {
    if (toontBewaard) statusRef.current?.scrollIntoView?.({ block: 'nearest', behavior: scrollGedrag() })
  }, [toontBewaard])

  function explain() {
    setThanks(0)
    setExplaining(true)
  }

  async function submit(oordeel, tekst = '') {
    setError(null)
    setThanks(0)
    try {
      await onSubmit(oordeel, tekst)
      setExplaining(false)
      setToelichting('')
      setMetBewaard(oordeel === 'up')
      setThanks(n => n + 1)
    } catch (e) {
      setError(`Feedback opslaan lukt niet: ${e.message}`)
    }
  }

  return (
    <div className={`answer-feedback${toontBewaard ? ' answer-feedback--bewaard' : ''}`}>
      <button type="button" className="answer-feedback-btn" aria-label="Goed antwoord" aria-pressed={value === 'up'}
        onClick={() => submit('up')}>👍</button>
      <button type="button" className="answer-feedback-btn" aria-label="Fout antwoord" aria-pressed={value === 'down'}
        onClick={explain}>👎</button>
      {/* Always rendered: a live region inserted together with its text is often not announced. Empty it takes
          no room, so no answer gets an extra line; after a thumbs-up it reads the thanks plus BEWAARD (#807). */}
      <span ref={statusRef} className="answer-feedback-confirm" role="status">
        {thanks > 0 && THANKS}
        {toontBewaard && <>{' '}<span className="answer-feedback-bewaard">{BEWAARD}</span></>}
      </span>
      {explaining && (
        <form className="answer-feedback-form" onSubmit={e => { e.preventDefault(); submit('down', toelichting) }}>
          <textarea ref={fieldRef} rows={2} maxLength={2000} value={toelichting}
            aria-label="Wat klopt er niet? (optioneel)" placeholder="Wat klopt er niet? (optioneel)"
            aria-describedby={bewaardId} onChange={e => setToelichting(e.target.value)} />
          <p className="answer-feedback-bewaard" id={bewaardId}>{BEWAARD}</p>
          <div className="answer-feedback-actions">
            <button type="button" className="confirm-cancel" onClick={() => setExplaining(false)}>Annuleer</button>
            <button type="submit" className="confirm-primary">Verstuur</button>
          </div>
        </form>
      )}
      {error && <span className="answer-feedback-note" role="alert">{error}</span>}
    </div>
  )
}
