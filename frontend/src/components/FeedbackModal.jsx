import { Fragment, useEffect, useId, useRef, useState } from 'react'
import { useDialog } from '../hooks/useDialog'
import { fetchFeedbackQuestions, postFeedback } from '../api'

// "Anders" in a multi question is stored as 'Anders' or 'Anders: <what>' (core/feedback.py).
const OTHER = 'Anders'
const OTHER_PREFIX = `${OTHER}: `
const isOther = item => item === OTHER || item.startsWith(OTHER_PREFIX)

// The backend names the section generically ("Over jouw instelling"); with a chosen instelling it gets its name.
// The button that reveals that section (#666) is named the same way.
const GENERIC_INSTELLING = 'jouw instelling'
const sectionTitle = (section, instelling) => (instelling ? section.replace(GENERIC_INSTELLING, () => instelling) : section)
const EXTRA_BUTTON = `Help ons verder: vragen over ${GENERIC_INSTELLING}`
const countLabel = n => (n === 1 ? '1 vraag' : `${n} vragen`)

const hasValue = value => (Array.isArray(value) ? value.length > 0 : value.trim() !== '')

function MultiQuestion({ question, value, onChange }) {
  const chosen = value || []
  const other = chosen.find(isOther)
  const toggle = option => {
    if (option === OTHER) onChange(other === undefined ? [...chosen, OTHER] : chosen.filter(item => !isOther(item)))
    else onChange(chosen.includes(option) ? chosen.filter(item => item !== option) : [...chosen, option])
  }
  const setOtherDetail = detail => {
    const item = detail.trim() ? `${OTHER_PREFIX}${detail}` : OTHER
    onChange(chosen.map(c => (isOther(c) ? item : c)))
  }
  return (
    <fieldset className="feedback-question">
      <legend>{question.text}</legend>
      <div className="feedback-options multi">
        {question.options.map(option => (
          <label key={option} className="feedback-option">
            <input
              type="checkbox"
              value={option}
              checked={option === OTHER ? other !== undefined : chosen.includes(option)}
              onChange={() => toggle(option)}
            />
            <span>{option}</span>
          </label>
        ))}
      </div>
      {other !== undefined && (
        <input
          type="text"
          className="feedback-other"
          aria-label={`${OTHER}, welke?`}
          maxLength={200}
          value={other.slice(OTHER_PREFIX.length)}
          onChange={e => setOtherDetail(e.target.value)}
        />
      )}
    </fieldset>
  )
}

function Question({ question, value, onChange }) {
  const id = useId()
  if (question.type === 'multi') return <MultiQuestion question={question} value={value} onChange={onChange} />
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

// Per section (#665): the questions from its heading to the next one, and how many of them have an answer, so a
// long form on a phone says how much is left. Keyed by the question that carries the heading.
function sectionProgress(questions, answers) {
  const progress = new Map()
  let current = null
  for (const q of questions) {
    if (q.section) {
      current = { answered: 0, total: 0 }
      progress.set(q, current)
    }
    if (!current) continue
    current.total += 1
    if (hasValue(answers[q.id] ?? '')) current.answered += 1
  }
  return progress
}

// `headingRef`, if given, goes to the first section heading, which then takes focus from script only.
function QuestionList({ questions, answers, setAnswer, instelling, headingRef }) {
  const firstSection = questions.find(q => q.section)
  const progress = sectionProgress(questions, answers)
  return questions.map(q => (
    <Fragment key={q.id}>
      {q.section && (
        <>
          <h3
            className="feedback-section"
            ref={q === firstSection ? headingRef : undefined}
            tabIndex={headingRef && q === firstSection ? -1 : undefined}
          >
            {sectionTitle(q.section, instelling)}
          </h3>
          <p className="feedback-voortgang">{progress.get(q).answered} van {countLabel(progress.get(q).total)} beantwoord</p>
        </>
      )}
      <Question question={q} value={answers[q.id] ?? ''} onChange={v => setAnswer(q.id, v)} />
    </Fragment>
  ))
}

// `instelling` is what the user chose in the app's settings; '' when nothing was chosen (not the page's default).
export default function FeedbackModal({ workbook, instelling: chosen = '', onClose, onSubmitted }) {
  const instelling = (chosen || '').trim()
  const dialogRef = useDialog(onClose)
  const titleId = useId()
  const [questions, setQuestions] = useState(null)
  const [answers, setAnswers] = useState({})
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  // The questions flagged `extra` (about the institution, #666) stay hidden until the user chooses to answer them.
  const [showExtra, setShowExtra] = useState(false)
  const extraHeadingRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    fetchFeedbackQuestions()
      .then(qs => { if (!cancelled) setQuestions(qs) })
      .catch(err => { if (!cancelled) setError(`Vragen niet geladen: ${err.message}`) })
    return () => { cancelled = true }
  }, [])

  // The reveal button had focus and is gone: move it to the heading of what appeared.
  useEffect(() => { if (showExtra) extraHeadingRef.current?.focus() }, [showExtra])

  const hasAnswer = Object.values(answers).some(hasValue)
  const reportQuestions = questions?.filter(q => !q.extra) ?? []
  const extraQuestions = questions?.filter(q => q.extra) ?? []
  const setAnswer = (id, value) => setAnswers(prev => ({ ...prev, [id]: value }))

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
        instelling,
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
        <p className="feedback-intro">
          {instelling
            ? 'We bewaren je antwoorden, de titel van het rapport en je gekozen instelling bij je account, 90 dagen lang. Het gesprek verwijderen wist deze feedback niet.'
            : 'We bewaren je antwoorden en de titel van het rapport bij je account, 90 dagen lang. Het gesprek verwijderen wist deze feedback niet.'}
        </p>
        {extraQuestions.length > 0 && (
          <p className="feedback-intro">
            Na de vragen over het rapport kun je ervoor kiezen ook vragen over je instelling te beantwoorden. Ook die
            zijn optioneel; we bewaren die antwoorden op dezelfde manier.
          </p>
        )}
        {!questions && !error && <p role="status">Vragen worden geladen…</p>}
        <QuestionList questions={reportQuestions} answers={answers} setAnswer={setAnswer} instelling={instelling} />
        {extraQuestions.length > 0 && !showExtra && (
          <button type="button" className="feedback-extra-btn" onClick={() => setShowExtra(true)}>
            {sectionTitle(EXTRA_BUTTON, instelling)} ({countLabel(extraQuestions.length)})
          </button>
        )}
        {showExtra && (
          <QuestionList
            questions={extraQuestions}
            answers={answers}
            setAnswer={setAnswer}
            instelling={instelling}
            headingRef={extraHeadingRef}
          />
        )}
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
