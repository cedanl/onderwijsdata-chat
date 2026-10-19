import { NVT, bronnenTekst, citatieSamenvatting } from '../answerBlocks'
import { bronLink } from '../bronLink'

// De vaste bouwstenen onder een dataantwoord (#416): altijd dezelfde rijen in dezelfde volgorde,
// gevuld of met "n.v.t.". Telling en export zijn de bestaande onderdelen; ChatPage geeft ze mee.
const LABELS = { citaties: 'Citaties', telling: 'Telling', export: 'Export', bronnen: 'Bronnen' }

// Een bronregel linkt naar de bronpagina die de server meestuurt (#621); zonder veilige link blijft hij tekst.
function Bronregel({ bron, url }) {
  if (!url) return bron
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" aria-label={`${bron} (opent in een nieuw tabblad)`}>
      <span>{bron}</span>
    </a>
  )
}

export default function AnswerBlocks({ blocks, msg, telling = null, dataExport = null }) {
  const inhoud = {
    citaties: () => citatieSamenvatting(msg.citaties),
    telling: () => telling,
    export: () => dataExport,
    bronnen: () => (
      <ul className="answer-bronnen">
        {bronnenTekst(msg.bronnen).map(bron => (
          <li key={bron}><Bronregel bron={bron} url={bronLink(msg.bronlinks, bron)} /></li>
        ))}
      </ul>
    ),
  }
  return (
    <dl className="answer-blocks">
      {blocks.map(({ kind, status }) => (
        <div key={kind} className="answer-block" data-blok={kind} data-status={status}>
          <dt>{LABELS[kind]}</dt>
          <dd>{status === NVT ? <span className="answer-block-nvt">{NVT}</span> : inhoud[kind]()}</dd>
        </div>
      ))}
    </dl>
  )
}
