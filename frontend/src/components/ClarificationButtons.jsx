import { useState } from 'react'

// The options of a clarification card. What was chosen comes from the conversation (`answer`,
// see clarificationState), so a reloaded card shows the same as before (#109); the local
// choice only bridges the moment between the click and the question appearing.
export default function ClarificationButtons({ options, onSelect, busy, answer = null }) {
  const [clicked, setClicked] = useState(null)

  if (!options) return null

  const chosen = answer?.answered ? answer.choice : clicked
  const closed = !!(answer?.answered || clicked)

  const handleSelect = (label) => {
    if (busy || closed) return
    setClicked(label)
    onSelect(label)
  }

  return (
    <div className="clarification-btns">
      {options.map(opt => {
        const label = typeof opt === 'string' ? opt : opt.label
        const desc = typeof opt === 'object' ? opt.beschrijving : null
        const isSelected = chosen === label
        return (
          <button type="button" key={label} className={`clarification-btn${isSelected ? ' selected' : ''}`} onClick={() => handleSelect(label)} disabled={busy || closed}>
            {isSelected ? '✓ ' : ''}{label}{desc ? ` — ${desc}` : ''}
          </button>
        )
      })}
    </div>
  )
}
