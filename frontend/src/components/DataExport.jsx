import { useState } from 'react'
import { downloadDataCsv } from '../api'
import { CITATIE_CSV_BESTAND, citatiesToCsv } from '../citatieCsv'
import { exportKeys } from '../dataExport'
import { saveFile } from '../saveFile'

// A CSV download per table the answer was built on (#269); none for a free-text answer.
// A failed download says why and offers to ask the question again (CH-44): the table is
// gone from the server's memory, and only a new answer brings it back. Data the server fetched
// again after a restart says so (#472): its numbers may differ from the answer above.
//
// Without a table from the server, the cited numbers are the export (#544): built here from the
// citations the answer carries, so it works for every data answer and after a restart.
function saveCitaties(csv) {
  saveFile(new Blob([csv], { type: 'text/csv;charset=utf-8' }), CITATIE_CSV_BESTAND)
}

export default function DataExport({
  tools, citaties = null, settled, onHerhaal = null, busy = false, download = downloadDataCsv, save = saveCitaties,
}) {
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const keys = exportKeys(tools)
  const citatieCsv = keys.length ? null : citatiesToCsv(citaties)
  if (!settled || (!keys.length && !citatieCsv)) return null

  async function onClick(key) {
    setError(null)
    setNotice(null)
    try {
      setNotice((await download(key)) || null)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="data-export">
      {keys.map((key, i) => (
        <button key={key} type="button" className="data-export-btn" onClick={() => onClick(key)}>
          {keys.length === 1 ? 'Download data als CSV' : `Tabel ${i + 1} als CSV`}
        </button>
      ))}
      {citatieCsv && (
        <button type="button" className="data-export-btn" onClick={() => save(citatieCsv)}>
          Download cijfers als CSV
        </button>
      )}
      {notice && (
        <div className="data-export-error" role="status">
          Let op: deze data is {notice}. De cijfers kunnen afwijken van het antwoord hierboven.
        </div>
      )}
      {error && (
        <div className="data-export-error" role="alert">
          {error}
          {onHerhaal && (
            <button type="button" className="message-continue" disabled={busy} onClick={onHerhaal}>
              Vraag opnieuw stellen
            </button>
          )}
        </div>
      )}
    </div>
  )
}
