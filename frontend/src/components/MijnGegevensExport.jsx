import { useEffect, useRef, useState } from 'react'
import { downloadMijnGegevens } from '../api'
import { saveFile } from '../saveFile'

// "Exporteer al mijn gegevens" (#645, AVG art. 15): alles wat de server onder dit account bewaart, als één
// JSON-bestand. De foutmelding is een vaste zin, nooit de technische fout (zoals "API 500" of
// "Failed to fetch"). Een verlopen sessie eindigt in de api-helper, zoals bij elke andere aanroep.
// Tijdens het exporteren is de knop uitgeschakeld en verliest hij de focus; daarna krijgt hij die terug,
// zodat wie met het toetsenbord werkt op dezelfde plek in de dialoog blijft.
export const EXPORT_MISLUKT = 'Het exporteren is niet gelukt. Probeer het later opnieuw.'
export const EXPORT_GELUKT = 'Je gegevens zijn gedownload als JSON-bestand.'

export default function MijnGegevensExport({ download = downloadMijnGegevens, save = saveFile }) {
  const [busy, setBusy] = useState(false)
  const [melding, setMelding] = useState(null)
  const buttonRef = useRef(null)
  const focusTerug = useRef(false)

  useEffect(() => {
    if (busy || !focusTerug.current) return
    focusTerug.current = false
    buttonRef.current?.focus()
  }, [busy])

  async function onClick() {
    if (busy) return
    focusTerug.current = document.activeElement === buttonRef.current
    setBusy(true)
    setMelding(null)
    try {
      await download({ save })
      setMelding('gelukt')
    } catch {
      setMelding('mislukt')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mijn-gegevens-export">
      <button type="button" ref={buttonRef} className="mijn-gegevens-export-btn" onClick={onClick} disabled={busy}
        aria-busy={busy ? 'true' : 'false'}>
        {busy ? 'Bezig met exporteren…' : 'Exporteer al mijn gegevens'}
      </button>
      {melding === 'mislukt' && (
        <p className="mijn-gegevens-export-melding mijn-gegevens-export-melding--fout" role="alert">{EXPORT_MISLUKT}</p>
      )}
      {melding === 'gelukt' && <p className="mijn-gegevens-export-melding" role="status">{EXPORT_GELUKT}</p>}
    </div>
  )
}
