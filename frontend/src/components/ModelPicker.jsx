import { useId } from 'react'

const plainLabel = m => (m.description ? `${m.name} — ${m.description}` : m.name)

// Option text per model (#496, F10): "name — description". Two models that would read the same
// (the same model via two providers) get their provider in parentheses, so the list stays distinguishable.
export function modelOptionLabels(models) {
  const plain = models.map(plainLabel)
  return plain.map((label, i) => {
    const twin = plain.some((other, j) => j !== i && other === label)
    return twin && models[i].provider ? `${label} (${models[i].provider})` : label
  })
}

// The provider of the chosen model stays visible as a caption, not tucked away (#496, F10).
export default function ModelPicker({ models, value, onChange }) {
  const captionId = useId()
  const labels = modelOptionLabels(models)
  const provider = models.find(m => m.id === value)?.provider
  return (
    <div className="model-picker">
      <div className="model-picker-control">
        <select aria-label="Model" aria-describedby={provider ? captionId : undefined} value={value} onChange={e => onChange(e.target.value)}>
          {models.map((m, i) => (
            <option key={m.id} value={m.id}>{labels[i]}</option>
          ))}
        </select>
        <svg className="model-picker-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
      {provider && <span id={captionId} className="model-picker-provider">{`Via ${provider}`}</span>}
    </div>
  )
}
