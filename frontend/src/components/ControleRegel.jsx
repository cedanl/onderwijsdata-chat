import { KOP, NIET_GECONTROLEERD, controleSamenvatting } from '../controleRegel'

// De regel "Wat is gecontroleerd" onder een data-antwoord (#1260), standaard ingeklapt. Uit het veld `controles` van de
// server; zonder dat veld (een antwoord van vóór #1260) geen regel. De vaste zin over wat níét gecontroleerd is, staat
// er altijd in, ook ingeklapt in de DOM: een schermlezer en een kopie lezen hem mee.
export default function ControleRegel({ controles }) {
  const samenvatting = controleSamenvatting(controles)
  if (!samenvatting) return null
  return (
    <details className="controle-regel">
      <summary>{KOP}: {samenvatting.kop}</summary>
      {samenvatting.details.map(zin => <p key={zin}>{zin}</p>)}
      <p className="controle-regel-niet">{NIET_GECONTROLEERD}</p>
    </details>
  )
}
