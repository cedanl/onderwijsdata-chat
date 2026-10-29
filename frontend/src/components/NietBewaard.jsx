import { useWorkbookDownload } from './WorkbookDownload'

// Een gesprek of rapport dat de server niet kreeg (#785): de melding blijft staan tot het wel lukt, in plaats van
// stil te falen terwijl het gesprek al in de zijbalk staat. Een 413 is niet met opnieuw proberen op te lossen.
const TE_GROOT = 413

export function GesprekNietBewaard({ status, onOpnieuw }) {
  if (status === TE_GROOT) {
    return (
      <p className="niet-bewaard" role="alert">
        Dit gesprek is te groot om op de server te bewaren en staat alleen in deze browser. Begin een nieuw gesprek
        om verder te gaan; exporteer dit gesprek als je het wilt houden.
      </p>
    )
  }
  return (
    <p className="niet-bewaard" role="alert">
      Dit gesprek is niet bewaard op de server.
      <button type="button" className="niet-bewaard-actie" onClick={onOpnieuw}>Opnieuw proberen</button>
    </p>
  )
}

// Het rapport bestaat alleen nog hier: zonder download is het weg als de pagina sluit.
export function RapportNietBewaard({ workbook, status, instelling, onOpnieuw }) {
  const { download, error } = useWorkbookDownload(workbook, instelling)
  return (
    <p className="niet-bewaard" role="alert">
      {status === TE_GROOT ? 'Dit rapport is te groot om op de server te bewaren.' : 'Dit rapport is niet bewaard op de server.'}
      {status !== TE_GROOT && <button type="button" className="niet-bewaard-actie" onClick={onOpnieuw}>Opnieuw proberen</button>}
      <button type="button" className="niet-bewaard-actie" onClick={download}>Download als HTML</button>
      {error && <span className="wb-download-error">{error}</span>}
    </p>
  )
}
