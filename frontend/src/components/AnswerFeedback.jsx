import { useEffect, useRef, useState } from 'react'

// 👍/👎 under an answer (#248). A thumbs-down asks what is wrong first: with the
// trace the server adds, that makes it a reproducible bug report.
export default function AnswerFeedback({ value, onSubmit }) {
  const [explaining, setExplaining] = useState(false)
  const [toelichting, setToelichting] = useState('')
  const [error, setError] = useState(null)
  const [thanks, setThanks] = useState(false)
  const fieldRef = useRef(null)

  useEffect(() => {
    if (explaining) fieldRef.current?.focus()
  }, [explaining])

  async function submit(oordeel, tekst = '') {
    setError(null)
    try {
      await onSubmit(oordeel, tekst)
      setExplaining(false)
      setToelichting('')
      setThanks(true)
    } catch (e) {
      setError(`Feedback opslaan lukt niet: ${e.message}`)
    }
  }

  return (
    <div className="answer-feedback">
      <button type="button" className="answer-feedback-btn" aria-label="Goed antwoord" aria-pressed={value === 'up'}
        onClick={() => submit('up')}>👍</button>
      <button type="button" className="answer-feedback-btn" aria-label="Fout antwoord" aria-pressed={value === 'down'}
        onClick={() => setExplaining(true)}>👎</button>
      {thanks && !explaining && <span className="answer-feedback-note" role="status">Bedankt!</span>}
      {explaining && (
        <form className="answer-feedback-form" onSubmit={e => { e.preventDefault(); submit('down', toelichting) }}>
          <textarea ref={fieldRef} rows={2} maxLength={2000} value={toelichting}
            aria-label="Wat klopt er niet? (optioneel)" placeholder="Wat klopt er niet? (optioneel)"
            onChange={e => setToelichting(e.target.value)} />
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
