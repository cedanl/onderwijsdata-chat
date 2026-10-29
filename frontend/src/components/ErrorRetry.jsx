// Herstelpad onder een foutmelding (#333): dezelfde vraag opnieuw, of met een ander model.
// "Maximaal aantal stappen" of een limiet bij één model lukt vaak wél bij een ander.
// Een interne fout (#404) faalt bij elk model gelijk: dan alleen 'Opnieuw'.

// An error, a partial answer after the step budget ran out (#405), or a question the time limit stopped (#775):
// all get the retry buttons. The stop button does not: stopping was the user's own choice.
export const offersRetry = msg => !!(msg.isError || msg.partial || msg.timeout)

// A failure that a later answer has followed is history (#703): the question got its answer another way, so the
// buttons would only offer to ask it again. The message itself stays in the conversation.
const isAnswer = m => m.role === 'assistant' && !m.isError && !!m.done
export const offersRetryAt = (messages, index) => {
  const msg = messages[index]
  if (!offersRetry(msg)) return false
  return !((msg.isError || msg.timeout) && messages.slice(index + 1).some(isAnswer))
}

export function alternativeModel(models, failedModel) {
  return models.find(m => m.id !== failedModel) ?? null
}

export default function ErrorRetry({ question, failedModel, models = [], modelafhankelijk = true, busy, onRetry, herstel = null, onRapport = null }) {
  if (herstel === 'rapport') return <RapportRetry question={question} busy={busy} onRetry={onRetry} onRapport={onRapport} />
  if (!question) return null
  const alternative = modelafhankelijk ? alternativeModel(models, failedModel) : null
  return (
    <div className="message-retry">
      <button type="button" className="message-continue" disabled={busy} onClick={() => onRetry(question)}>
        Opnieuw
      </button>
      {alternative && (
        <button type="button" className="message-continue" disabled={busy} onClick={() => onRetry(question, alternative.id)}>
          Opnieuw met {alternative.name}
        </button>
      )}
    </div>
  )
}

// Een geweigerd rapport (#515): het rapport opnieuw maken, of de vraag opnieuw stellen.
// Een ander model biedt het niet aan: de controle hield het rapport tegen, niet het model.
function RapportRetry({ question, busy, onRetry, onRapport }) {
  if (!question && !onRapport) return null
  return (
    <div className="message-retry">
      {onRapport && (
        <button type="button" className="message-continue" disabled={busy} onClick={() => onRapport()}>
          Opnieuw proberen
        </button>
      )}
      {question && (
        <button type="button" className="message-continue" disabled={busy} onClick={() => onRetry(question)}>
          Vraag opnieuw stellen
        </button>
      )}
    </div>
  )
}
