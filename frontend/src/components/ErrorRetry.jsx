// Herstelpad onder een foutmelding (#333): dezelfde vraag opnieuw, of met een ander model.
// "Maximaal aantal stappen" of een limiet bij één model lukt vaak wél bij een ander.

export function alternativeModel(models, failedModel) {
  return models.find(m => m.id !== failedModel) ?? null
}

export default function ErrorRetry({ question, failedModel, models = [], busy, onRetry }) {
  if (!question) return null
  const alternative = alternativeModel(models, failedModel)
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
