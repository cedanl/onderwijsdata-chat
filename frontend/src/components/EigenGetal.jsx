import { useId, useState } from 'react'
import { eigenGetalFout } from '../eigenGetal'

// "Wijkt af van je eigen cijfer?" onder een antwoord met precies één hoofdgetal (#1258). De server zet `hoofdgetal`
// alleen bij zo'n antwoord; de knop opent een veld voor één getal, de server legt het naast het onze en noemt de
// bekende redenen voor een verschil, met hun grootte uit code. Geen vrije tekst: wat geen getal is, gaat niet weg.
export default function EigenGetal({ hoofdgetal, onVerstuur, busy = false }) {
  const [open, setOpen] = useState(false)
  const [waarde, setWaarde] = useState('')
  const [fout, setFout] = useState(null)
  const veldId = useId()
  const uitlegId = useId()
  const foutId = useId()
  if (!hoofdgetal?.id || !onVerstuur) return null

  if (!open) {
    return (
      <div className="eigen-getal">
        <button type="button" className="message-continue" onClick={() => setOpen(true)} disabled={busy}>
          Wijkt af van je eigen cijfer?
        </button>
      </div>
    )
  }

  const verstuur = (e) => {
    e.preventDefault()
    const melding = eigenGetalFout(waarde)
    setFout(melding)
    if (melding) return
    if (onVerstuur(hoofdgetal.id, waarde.trim())) {
      setOpen(false)
      setWaarde('')
    }
  }

  return (
    <form className="eigen-getal eigen-getal-open" onSubmit={verstuur} noValidate>
      <label htmlFor={veldId} className="eigen-getal-label">Je eigen cijfer</label>
      <div className="eigen-getal-rij">
        <input
          id={veldId}
          className="eigen-getal-veld"
          type="text"
          inputMode="numeric"
          autoComplete="off"
          value={waarde}
          onChange={e => { setWaarde(e.target.value); setFout(null) }}
          aria-describedby={fout ? `${uitlegId} ${foutId}` : uitlegId}
          aria-invalid={fout ? 'true' : undefined}
          maxLength={20}
        />
        <button type="submit" className="eigen-getal-knop" disabled={busy}>Vergelijk</button>
        <button type="button" className="message-continue" onClick={() => { setOpen(false); setFout(null) }}>Annuleer</button>
      </div>
      {fout && <div id={foutId} className="eigen-getal-fout" role="alert">{fout}</div>}
      <p id={uitlegId} className="eigen-getal-uitleg">
        Alleen een getal, bijvoorbeeld uit je eigen administratie of een jaarverslag. De app zet het naast het getal
        hierboven en noemt de bekende redenen voor een verschil, met hun grootte als die uit open data volgt. Je getal
        is jouw invoer: het staat in het gesprek, maar telt nergens als bron.
      </p>
    </form>
  )
}
