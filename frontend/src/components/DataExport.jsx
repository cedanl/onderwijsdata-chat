import { useState } from 'react'
import { downloadDataCsv } from '../api'
import { exportKeys } from '../dataExport'

// A CSV download per table the answer was built on (#269); none for a free-text answer.
// A failed download says why and offers to ask the question again (CH-44): the table is
// gone from the server's memory, and only a new answer brings it back.
export default function DataExport({ tools, settled, onHerhaal = null, busy = false, download = downloadDataCsv }) {
  const [error, setError] = useState(null)
  const keys = exportKeys(tools)
  if (!settled || !keys.length) return null

  async function onClick(key) {
    setError(null)
    try {
      await download(key)
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
