import { NVT, citatieSamenvatting } from '../answerBlocks'

// De vaste bouwstenen onder een dataantwoord (#416): altijd dezelfde rijen in dezelfde volgorde,
// gevuld of met "n.v.t.". Telling en export zijn de bestaande onderdelen; ChatPage geeft ze mee.
const LABELS = { citaties: 'Citaties', telling: 'Telling', export: 'Export', bronnen: 'Bronnen' }

export default function AnswerBlocks({ blocks, msg, telling = null, dataExport = null }) {
  const inhoud = {
    citaties: () => citatieSamenvatting(msg.citaties),
    telling: () => telling,
    export: () => dataExport,
    bronnen: () => (
      <ul className="answer-bronnen">
        {msg.bronnen.map(bron => <li key={bron}>{bron}</li>)}
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
