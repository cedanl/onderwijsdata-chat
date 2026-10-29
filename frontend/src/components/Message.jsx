import { useId } from 'react'
import { useMediaQuery, NARROW_SCREEN } from '../hooks/useMediaQuery'
import DataExport from './DataExport'
import AnswerBlocks from './AnswerBlocks'
import IngetrokkenVersies from './IngetrokkenVersies'
import { hasExport } from '../dataExport'
import AnswerFeedback from './AnswerFeedback'
import CopyButton from './CopyButton'
import ErrorRetry from './ErrorRetry'
import ClarificationButtons from './ClarificationButtons'
import { answerBlocks, metBronnen } from '../answerBlocks'
import { vervolgvragenTekst } from '../vervolgvragen'
import { ReasoningPanel, TellingDetails, MessageContent, isAwaitingFirstToken } from './MessageContent'
import { PlotlyFigure } from './PlotlyFigure'

// De bubbel van één bericht: vraag, antwoord, grafieken, verduidelijking en de knoppen eronder. Uit ChatPage.jsx
// gehaald (#696); ChatPage exporteert Message opnieuw, zodat bestaande imports blijven werken.

function userInitials(settings) {
  if (settings.instelling) {
    const words = settings.instelling.trim().split(/\s+/)
    return words.length >= 2
      ? (words[0][0] + words[1][0]).toUpperCase()
      : words[0].slice(0, 2).toUpperCase()
  }
  if (settings.functie) return settings.functie.slice(0, 2).toUpperCase()
  return '?'
}

// Questions to click under a message. The "Verken …" starters send one at once (onPick = send); a
// follow-up question goes into the input box (#364). `label` names the group; with `kop` it also
// stands above the buttons.
function QuestionButtons({ questions, onPick, busy, label, kop = false }) {
  const kopId = useId()
  if (!questions?.length) return null
  const naam = kop ? { 'aria-labelledby': kopId } : { 'aria-label': label }
  return (
    <div className="clarification-btns question-buttons" role="group" {...naam}>
      {kop && <div id={kopId} className="question-buttons-kop">{label}</div>}
      {questions.map(q => (
        <button type="button" key={q} className="suggested-btn" onClick={() => !busy && onPick(q)}>{q}</button>
      ))}
    </div>
  )
}

function hasAssistantContent(msg) {
  return !!(
    msg.content ||
    msg.figures?.length ||
    msg.clarification ||
    msg.starterQuestions ||
    msg.stopped ||
    msg.interrupted ||
    msg.empty
  )
}

// onVervolgvraag: only the last answer gets it; its follow-up questions then show while nothing runs (#364).
// onAndersFormuleren: a clarification card whose question is known gets it, also while something runs (#494).
// figures: de grafieken in deze bubbel; zonder opgave die van het bericht zelf (#610, figuurGroep.js).
// verbinding: of de chat nu verbonden is; een afgebroken antwoord zegt dan dat opnieuw proberen kan (#617).
export function Message({ msg, figures = null, verbinding = false, onClarification, onSend, busy, settled = true, settings = {}, retry = null, herhaal = null, modelLabel = null, clarification = null, feedback = null, onVervolgvraag = null, onAndersFormuleren = null }) {
  const smal = useMediaQuery(NARROW_SCREEN)
  if (msg.role === 'user') {
    return (
      <div className="message user">
        <div className="message-avatar">{userInitials(settings)}</div>
        <div className="message-bubble">
          {msg.content && <CopyButton text={msg.content} className="copy-btn-message" />}
          {msg.content}
        </div>
        {/* Altijd aanwezig, tijdens een antwoord verborgen: de knop neemt zijn plek in de rij in, en een knop die pas
            bij het eind van het antwoord komt, verbreedde elke vraag en schoof de bubbel opzij (#661). */}
        <button type="button"
          className="resend-btn"
          title="Opnieuw sturen"
          aria-label="Vraag opnieuw sturen"
          disabled={busy}
          onClick={() => onSend(msg.content)}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
            <polyline points="1 4 1 10 7 10" />
            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
          </svg>
        </button>
      </div>
    )
  }

  const awaiting = isAwaitingFirstToken(msg)
  // Een grafiek komt binnen zodra create_plot draait, vóór de eindtekst; in de bubbel staat ze onder de tekst, dus
  // op een telefoon duwde elke gestreamde regel haar omlaag (CLS 0,096, #639). Daar verschijnt ze pas als het
  // antwoord compleet is. Op een breed scherm zijn het weinig regels (0,016), en later tonen kostte er meer (0,054).
  const figuren = !smal || msg.done || !busy ? (figures ?? msg.figures ?? []) : []
  const inhoud = hasAssistantContent(msg) || figuren.length > 0
  // A round with only data steps has no text, but its tables can still be downloaded.
  const exportable = settled && hasExport(msg)
  // A data answer gets its fixed building blocks; any other message renders as before (#416).
  const blocks = answerBlocks(msg, { settled })
  const dataExport = (
    <DataExport tools={msg.tools} citaties={msg.citaties} settled={settled} onHerhaal={herhaal || null} busy={busy} />
  )
  if (!awaiting && !msg.tools?.length && !msg.vervangen?.length && !inhoud) return null

  return (
    <div className="message assistant">
      <div className="message-avatar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
        </svg>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, minWidth: 0 }}>
        <ReasoningPanel tools={msg.tools} tussentekst={msg.tussentekst} isDone={msg.done} heeftTekst={!!msg.content} />
        <IngetrokkenVersies versies={msg.vervangen} eindtekst={msg.content || ''} />
        {(awaiting || exportable || inhoud) && (
          <div className={`message-bubble message-bubble-assistant${msg.isError ? ' message-bubble-error' : ''}`}>
            {msg.content && <CopyButton text={metBronnen(msg.content, msg.bronnen)} className="copy-btn-message" />}
            <MessageContent msg={msg} blocks={blocks} />
            {/* Direct onder de tekst (#429): een ingehouden antwoord zegt "Hieronder staat wat er
                niet klopte", en grafieken met hun knoppen mogen daar niet tussen staan. */}
            {msg.controle?.map(zin => <div key={zin} className="message-controle">Let op: {zin}</div>)}
            {/* Vóór de blokken en de vervolgvragen: wat na de grafiek landt, verschuift hem niet (#610). */}
            {figuren.map((fig, i) => (
              <PlotlyFigure key={fig.label || i} figureJson={fig.json} label={fig.label} />
            ))}
            {blocks
              ? <AnswerBlocks blocks={blocks} msg={msg} telling={<TellingDetails msg={msg} kop={false} />} dataExport={dataExport} />
              : dataExport}
            <ClarificationButtons options={msg.clarification} onSelect={onClarification} busy={busy} answer={clarification} onAndersFormuleren={onAndersFormuleren}
              vraag={typeof msg.content === 'string' ? msg.content : null} />
            <QuestionButtons questions={msg.starterQuestions} onPick={onSend} busy={busy} label="Voorbeeldvragen" />
            {onVervolgvraag && !busy && (
              <QuestionButtons questions={vervolgvragenTekst(msg.vervolgvragen)} onPick={onVervolgvraag} busy={busy} label="Vervolgvragen" kop />
            )}
            {msg.stopped && !msg.timeout && <div className="message-stopped">Genereren gestopt</div>}
            {/* De tijdsgrens stopte de vraag (#775): de reden blijft staan, met de knoppen hieronder. role="status":
                ook wie wegkeek of een schermlezer gebruikt, hoort waarom. */}
            {msg.timeout && (
              <div className="message-stopped" role="status">{msg.stopreden || 'De vraag is gestopt: de tijd was om.'}</div>
            )}
            {msg.truncated && (
              <div className="message-stopped">
                Antwoord afgebroken: de maximale lengte is bereikt.{' '}
                <button type="button" className="message-continue" onClick={() => onSend('Ga verder waar je gebleven was.')} disabled={busy}>
                  Ga verder
                </button>
              </div>
            )}
            {msg.interrupted && (
              /* Zodra de verbinding terug is, zegt de regel dat en licht de knop op (#617): wie in de trein weer
                 bereik heeft, hoeft de knop niet zelf te bedenken. Alleen als er een knop is (een ingeladen gesprek
                 zonder vraag ervoor heeft er geen); geen automatische tweede run (die telt mee in de berichtlimiet,
                 #444). aria-live: ook voor een schermlezer een melding, geen tweede knop. */
              <div className={`message-stopped${verbinding && herhaal ? ' verbinding-terug' : ''}`} role="status" aria-live="polite">
                {verbinding && herhaal ? 'Verbinding terug — probeer opnieuw' : 'Verbinding verbroken — antwoord onvolledig'}
                {/* Herstel bij de fout (#547, WCAG 3.3.3): de vraag ervoor opnieuw, zonder ander model. */}
                {herhaal && (
                  <>
                    {' '}
                    <button type="button" className={`message-continue${verbinding ? ' message-continue--licht' : ''}`} onClick={herhaal} disabled={busy}>
                      Probeer opnieuw
                    </button>
                  </>
                )}
              </div>
            )}
            {msg.empty && <div className="message-stopped">Geen antwoord ontvangen — stuur je vraag opnieuw</div>}
            {retry && (
              <ErrorRetry
                question={retry.question?.content}
                failedModel={retry.question?.model || retry.selectedModel}
                models={retry.models}
                modelafhankelijk={retry.modelafhankelijk}
                busy={busy || !!retry.reportBusy}
                onRetry={retry.onRetry}
                herstel={retry.herstel}
                onRapport={retry.onRapport}
              />
            )}
          </div>
        )}
        {modelLabel && <div className="message-model">Antwoord van {modelLabel}</div>}
        {feedback && <AnswerFeedback value={feedback.value} onSubmit={feedback.onSubmit} />}
      </div>
    </div>
  )
}
