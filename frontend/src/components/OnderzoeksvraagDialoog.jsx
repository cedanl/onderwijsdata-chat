import { useEffect, useId, useRef, useState } from 'react'
import { useDialog } from '../hooks/useDialog'

// Before a report (#751): the research question it answers, filled in and open to change (#732). Genereer, or Enter
// as in the chat input, sends the text along; an empty field sends none, and the server takes the first question.
// Escape or Annuleren closes without a report.

// The field grows with the question, so all of it shows; max-height in styles.css caps it on a small screen.
function pasHoogteAan(veld) {
  veld.style.height = 'auto'
  veld.style.height = `${veld.scrollHeight + veld.offsetHeight - veld.clientHeight}px`
}

export default function OnderzoeksvraagDialoog({ voorstel, max, onGenereer, onClose }) {
  const dialogRef = useDialog(onClose)
  const veldRef = useRef(null)
  const labelId = useId()
  const veldId = useId()
  const uitlegId = useId()
  const [tekst, setTekst] = useState(() => voorstel.slice(0, max))

  // useDialog puts the focus in the field; the cursor goes to the end, where a narrowing gets added.
  useEffect(() => {
    const veld = veldRef.current
    pasHoogteAan(veld)
    veld.setSelectionRange(veld.value.length, veld.value.length)
  }, [])

  function genereer(e) {
    e.preventDefault()
    onGenereer(tekst.trim())
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) genereer(e)
  }

  return (
    <div className="confirm-overlay">
      <form className="confirm-dialog onderzoeksvraag-dialoog" ref={dialogRef} role="dialog" aria-modal="true"
        aria-labelledby={labelId} tabIndex={-1} onSubmit={genereer}>
        <label className="onderzoeksvraag-label" id={labelId} htmlFor={veldId}>Onderzoeksvraag van het rapport</label>
        <textarea
          ref={veldRef}
          id={veldId}
          className="onderzoeksvraag-veld"
          rows={2}
          value={tekst}
          maxLength={max}
          aria-describedby={uitlegId}
          onChange={e => { setTekst(e.target.value); pasHoogteAan(e.target) }}
          onKeyDown={onKeyDown}
        />
        <p className="onderzoeksvraag-uitleg" id={uitlegId}>
          Het rapport beantwoordt deze vraag. Pas haar aan om af te bakenen. Leeg laten: het rapport neemt je eerste vraag.
        </p>
        <div className="confirm-actions">
          <button type="button" className="confirm-cancel" onClick={onClose}>Annuleren</button>
          <button type="submit" className="confirm-primary">Genereer</button>
        </div>
      </form>
    </div>
  )
}
