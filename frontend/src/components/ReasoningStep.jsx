// One step in the reasoning card. Green only when the step delivered; an empty filter or a
// failed step says so, with the values that do exist when the server sent them (#386).
export default function ReasoningStep({ tool }) {
  const status = tool.status && tool.done ? ` ${tool.status}` : ''
  const suggesties = Object.entries(tool.suggesties || {})
  return (
    <div className={`reasoning-step${status}`}>
      <div className={`reasoning-step-dot${tool.done ? ' done' : ''}${status}`} />
      <div>
        <span>{(tool.done && tool.statusLabel) || tool.label}</span>
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
