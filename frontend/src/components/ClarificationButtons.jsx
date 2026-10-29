import { useState } from 'react'

// The options of a clarification card. What was chosen comes from the conversation (`answer`,
// see clarificationState), so a reloaded card shows the same as before (#109); the local
// choice only bridges the moment between the click and the question appearing.
// onAndersFormuleren: puts the question back in the input box (#494). Unlike the options it works
// in every state, and it comes last, so whoever picks an option at once does not meet it first.
// vraag: the card's question, which names the group of options for a screen reader (#541).
export default function ClarificationButtons({ options, onSelect, busy, answer = null, onAndersFormuleren = null, vraag = null }) {
  const [clicked, setClicked] = useState(null)

  if (!options) return null

  const chosen = answer?.answered ? answer.choice : clicked
  const closed = !!(answer?.answered || clicked)

  // Pas dicht als de keuze echt wegging (#774): zonder verbinding bleef de kaart anders op slot tot herladen.
  const handleSelect = (label) => {
    if (busy || closed) return
    if (onSelect(label)) setClicked(label)
  }

  return (
    <>
      <div className="clarification-btns" role="group" aria-label={vraag || 'Kies een optie'}>
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
      {onAndersFormuleren && (
        <button type="button" className="clarification-reformulate" onClick={() => onAndersFormuleren()}
          aria-label="Anders formuleren: zet je oorspronkelijke vraag terug in het invoerveld">
          Anders formuleren
        </button>
      )}
    </>
  )
}
