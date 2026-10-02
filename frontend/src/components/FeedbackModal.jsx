import { useEffect, useId, useState } from 'react'
import { useDialog } from '../hooks/useDialog'
import { fetchFeedbackQuestions, postFeedback } from '../api'

function Question({ question, value, onChange }) {
  const id = useId()
  if (question.type === 'text') {
    return (
      <div className="feedback-question">
        <label htmlFor={id}>{question.text}</label>
        <textarea id={id} rows={3} maxLength={2000} value={value} onChange={e => onChange(e.target.value)} />
      </div>
    )
  }
  return (
    <fieldset className="feedback-question">
      <legend>{question.text}</legend>
      <div className={`feedback-options ${question.type}`}>
        {question.type === 'scale' && question.labels && <span className="feedback-scale-label">{question.labels[0]}</span>}
        {question.options.map(option => (
          <label key={option} className="feedback-option">
            <input
              type="radio"
              name={id}
              value={option}
              checked={value === option}
              onChange={() => onChange(option)}
            />
            <span>{option}</span>
          </label>
        ))}
        {question.type === 'scale' && question.labels && <span className="feedback-scale-label">{question.labels[1]}</span>}
      </div>
    </fieldset>
  )
}

export default function FeedbackModal({ workbook, onClose, onSubmitted }) {
  const dialogRef = useDialog(onClose)
  const titleId = useId()
  const [questions, setQuestions] = useState(null)
  const [answers, setAnswers] = useState({})
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetchFeedbackQuestions()
      .then(qs => { if (!cancelled) setQuestions(qs) })
      .catch(err => { if (!cancelled) setError(`Vragen niet geladen: ${err.message}`) })
    return () => { cancelled = true }
  }, [])

  const hasAnswer = Object.values(answers).some(v => v.trim())

  async function handleSubmit(e) {
    e.preventDefault()
    if (!hasAnswer || sending) return
    setSending(true)
    setError(null)
    try {
      await postFeedback({
        workbook_id: workbook.id,
        report_type: workbook.type || '',
        report_title: workbook.title || '',
        answers,
      })
      onSubmitted()
    } catch (err) {
      setError(`Feedback niet verstuurd: ${err.message}`)
      setSending(false)
    }
  }

  return (
    <div className="confirm-overlay">
      <form
        className="confirm-dialog feedback-dialog"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onSubmit={handleSubmit}
      >
        <h2 className="feedback-title" id={titleId}>Feedback geven</h2>
        <p className="feedback-intro">Alle vragen zijn optioneel. Je antwoorden helpen ons de rapporten te verbeteren.</p>
        {!questions && !error && <p role="status">Vragen worden geladen…</p>}
        {questions?.map(q => (
          <Question
            key={q.id}
            question={q}
            value={answers[q.id] ?? ''}
            onChange={v => setAnswers(prev => ({ ...prev, [q.id]: v }))}
          />
        ))}
        {error && <p role="alert" className="feedback-error">{error}</p>}
        <div className="confirm-actions">
          <button type="button" className="confirm-cancel" onClick={onClose}>Annuleren</button>
          <button type="submit" className="feedback-submit" disabled={!hasAnswer || sending}>
            {sending ? 'Versturen…' : 'Versturen'}
          </button>
        </div>
      </form>
    </div>
  )
}
