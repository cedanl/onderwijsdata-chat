// One step in the reasoning card. Green only when the step delivered; an empty filter or a
// failed step says so, with the values that do exist when the server sent them (#386).
// A failed step that a later attempt made good is dimmed and says so (#426).
const UITLEG = {
  recovered: 'Een volgende poging lukte; het antwoord gebruikt die.',
  error: 'Het filter kon niet op de data worden uitgevoerd.',
}

export default function ReasoningStep({ tool }) {
  const status = tool.status && tool.done ? ` ${tool.status}${tool.recovered ? ' recovered' : ''}` : ''
  const suggesties = tool.recovered ? [] : Object.entries(tool.suggesties || {})
  const uitleg = tool.done && (tool.recovered ? UITLEG.recovered : UITLEG[tool.status])
  return (
    <div className={`reasoning-step${status}`}>
      <div className={`reasoning-step-dot${tool.done ? ' done' : ''}${status}`} />
      <div>
        <span>{(tool.done && tool.statusLabel) || tool.label}</span>
        {uitleg && <p className="reasoning-step-uitleg">{uitleg}</p>}
        {suggesties.length > 0 && (
          <ul className="reasoning-step-hints">
            {suggesties.map(([kolom, waarden]) => (
              <li key={kolom}>{kolom}: {Array.isArray(waarden) ? waarden.join(', ') : waarden}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
