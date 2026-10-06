// Herstelpad onder een foutmelding (#333): dezelfde vraag opnieuw, of met een ander model.
// "Maximaal aantal stappen" of een limiet bij één model lukt vaak wél bij een ander.
// Een interne fout (#404) faalt bij elk model gelijk: dan alleen 'Opnieuw'.

// An error, or a partial answer after the step budget ran out (#405): both get the retry buttons.
export const offersRetry = msg => !!(msg.isError || msg.partial)

export function alternativeModel(models, failedModel) {
  return models.find(m => m.id !== failedModel) ?? null
}

export default function ErrorRetry({ question, failedModel, models = [], modelafhankelijk = true, busy, onRetry }) {
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
