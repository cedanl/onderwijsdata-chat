import { useState } from 'react'
import { downloadDataCsv } from '../api'
import { bewijsBestandsnaam, bewijsJson, heeftBewijs } from '../bewijsJson'
import { CITATIE_CSV_BESTAND, citatiesToCsv } from '../citatieCsv'
import { exportKeys } from '../dataExport'
import { saveFile } from '../saveFile'
import { metVoorbehoud } from '../voorbehoud'

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

// "Bewijs (JSON)" (#1244): the provenance the message already holds, built here (bewijsJson.js); no server route.
function saveBewijs(json, naam) {
  saveFile(new Blob([json], { type: 'application/json;charset=utf-8' }), naam)
}

// Wat een CSV van een antwoord bevat, in de app zelf (#1257); docs/reproducibility.md zegt hetzelfde.
export const CSV_UITLEG = 'Boven de tabel staan regels die met # beginnen: het Uitgangspunt, wat niet is meegeteld, Bron en '
  + 'definitie, de Let op-regels en wat is gecontroleerd, en daarna de bron, de selectie en de onderdrukte cellen. Een '
  + 'tabel met onderdrukte cellen heeft de kolom ondergrens: ja als er in die rij een onderdrukte cel valt, het getal is '
  + "dan ten minste zo groot. In pandas: read_csv(bestand, sep=';', comment='#')."

// `voorbehoud`: de regels die met elke export van dit antwoord meegaan (voorbehoud.js, #1257).
export default function DataExport({
  tools, citaties = null, settled, onHerhaal = null, busy = false, download = downloadDataCsv, save = saveCitaties,
  voorbehoud = [], bewijsVan = null, vraag = null, saveJson = saveBewijs,
}) {
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const keys = exportKeys(tools)
  const citatieCsv = keys.length ? null : metVoorbehoud(citatiesToCsv(citaties), voorbehoud)
  const metBewijs = heeftBewijs(bewijsVan)
  if (!settled || (!keys.length && !citatieCsv && !metBewijs)) return null

  async function onClick(key) {
    setError(null)
    setNotice(null)
    try {
      setNotice((await download(key, voorbehoud)) || null)
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
      {metBewijs && (
        <button type="button" className="bewijs-btn" onClick={() => saveJson(bewijsJson(bewijsVan), bewijsBestandsnaam(vraag))}>
          Bewijs (JSON)
        </button>
      )}
      {/* Alleen bij een CSV: een antwoord met alleen het bewijsbestand heeft geen CSV om uit te leggen. */}
      {(keys.length > 0 || citatieCsv) && (
        <details className="data-export-uitleg">
          <summary>Wat staat er in de CSV?</summary>
          <p>{CSV_UITLEG}</p>
        </details>
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
