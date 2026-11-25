import { VASTE_MAAT_UITLEG, vasteMaat, vasteMaatLabel, vastgelegdTekst } from '../vasteMaat'

// "Vaste maat: <naam>" onder een antwoord dat alleen op get_maat rust (#1242), met de teldefinitie en de vastlegging
// in een uitklap. De server zet het veld uit de stappen, nooit uit de modeltekst; zonder geldig veld staat er niets.
export default function VasteMaat({ waarde }) {
  const vm = vasteMaat(waarde)
  if (!vm) return null
  return (
    <details className="vaste-maat">
      <summary>{vasteMaatLabel(vm)}</summary>
      <div className="vaste-maat-uitleg">
        <p>{VASTE_MAAT_UITLEG}</p>
        <p>Teldefinitie: {vm.teldefinitie}</p>
        <p>{vastgelegdTekst(vm)}</p>
      </div>
    </details>
  )
}
