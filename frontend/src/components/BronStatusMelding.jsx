import { useBronStatus } from '../hooks/useBronStatus'

// Welke bronnen nu niet live zijn (#1057). Alleen dan staat er iets; zijn alle bronnen live, dan blijft de regio leeg en
// neemt ze geen ruimte in. De live-regio is altijd gemonteerd (zoals bij ConnectionStatus): een regio die samen met haar
// tekst verschijnt, wordt vaak niet voorgelezen. De tekst komt van de server, dus de melding noemt nooit meer dan de
// server prijsgeeft.
export default function BronStatusMelding() {
  const nietLive = useBronStatus()
  return (
    <div className="bronstatus" role="status" aria-live="polite">
      {nietLive.map(bron => (
        <p key={bron.bron} className="bronstatus-melding">{bron.tekst}</p>
      ))}
    </div>
  )
}
