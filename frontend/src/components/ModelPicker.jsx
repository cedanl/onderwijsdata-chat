export default function ModelPicker({ models, value, onChange }) {
  return (
    <div className="model-picker">
      <select value={value} onChange={e => onChange(e.target.value)}>
        {models.map(m => (
          <option key={m.id} value={m.id}>{m.name}{m.description ? ` — ${m.description}` : ''}</option>
        ))}
      </select>
      <svg className="model-picker-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </div>
  )
}
