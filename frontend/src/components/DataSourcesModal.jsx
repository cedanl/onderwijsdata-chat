/* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */
import { useEffect, useState } from 'react'
import { fetchCatalogCounts } from '../api'
import { useDialog } from '../hooks/useDialog'
import { useBronnenLijst } from '../bronnenLijst'

// Counts come from the catalog the app searches, so they cannot drift from it.
const withCount = (n, text) => (n ? `${n} ${text}` : text)

// One row per source that bronnenLijst() names (#1149): the same list as the welcome text of the chat and the intro of
// the homepage, so a source behind a key or flag (LCSK, WOPI) shows here exactly where it shows there. The counts only
// fill in numbers; they no longer decide which rows show. The link text says what the link does (#1150).
const RIJEN = {
  cbs: counts => [withCount(counts.CBS, 'datasets met onderwijsstatistieken'), 'Bekijk de CBS-catalogus', 'https://cedanl.github.io/onderwijsdata-chat/catalogus/cbs/'],
  duo: counts => [withCount(counts.DUO, 'open datasets: prognoses, diplomering, instroom, adressen'), 'Bekijk de DUO-catalogus', 'https://onderwijsdata.duo.nl'],
  rio: counts => [`Register van onderwijsinstellingen en opleidingen${counts.RIO ? ` (${counts.RIO} bestanden)` : ''}`, 'Bekijk de RIO-catalogus', 'https://cedanl.github.io/onderwijsdata-chat/catalogus/rio/'],
  uwv: () => ['Vacatures per provincie of gemeente (momentopname mei 2023)', 'Bekijk de UWV-data', 'https://data.overheid.nl/dataset/uwv-open-match-data'],
  roa: () => ['Schoolverlaters (SIS 2024) en arbeidsmarktprognoses tot 2030', 'Bekijk de ROA-data', 'https://doi.org/10.34894/DVQTOG'],
  inspectie: () => ['Oordelen van de Inspectie per mbo-instelling, en als context per vo-school', 'Bekijk de site van de Inspectie', 'https://www.onderwijsinspectie.nl'],
  lcsk: () => ['Studiekeuzedatabase: studenttevredenheid (NSE), studiesucces, numerus fixus en doorstroom per hbo- en wo-opleiding', 'Bekijk de uitleg van LCSK', 'https://lcsk.nl/over-ons/studiekeuzedata-raadplegen/'],
  unl: () => ['Personeel van de universiteiten (WOPI): fte en personen per universiteit', 'Bekijk de WOPI-cijfers van UNL', 'https://www.universiteitenvannederland.nl/downloadbare-gegevens-personeel'],
  wetten: () => ['Het wettelijk collegegeld per studiejaar. Dit staat als vaste tabel in de app; de app vraagt hier niets op.', 'Bekijk de regeling op wetten.nl', 'https://wetten.overheid.nl/BWBR0024005'],
}

export default function DataSourcesModal({ onClose }) {
  const [counts, setCounts] = useState({})
  const dialogRef = useDialog(onClose)
  const bronnen = useBronnenLijst()
  useEffect(() => {
    fetchCatalogCounts().then(setCounts).catch(() => {})
  }, [])

  return (
    <div className="modal-overlay" ref={dialogRef} onClick={onClose} role="dialog" aria-modal="true" aria-label="Databronnen" tabIndex={-1}>
      <button type="button" className="modal-overlay-close" onClick={onClose} aria-label="Sluiten">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 20, height: 20 }}>
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="section-label" style={{ marginBottom: 4 }}>Transparantie</div>
            <h2>Databronnen</h2>
          </div>
        </div>
        <div className="modal-body">
          <table className="modal-table">
            <thead>
              <tr><th>Bron</th><th>Inhoud</th><th>Meer weten</th></tr>
            </thead>
            <tbody>
              {bronnen.filter(({ sleutel }) => RIJEN[sleutel]).map(({ sleutel, naam }) => {
                const [inhoud, linktekst, href] = RIJEN[sleutel](counts)
                return (
                  <tr key={sleutel}>
                    <td><span className="source-name">{naam}</span></td>
                    <td><span className="source-desc">{inhoud}</span></td>
                    <td><a href={href} target="_blank" rel="noreferrer">{linktekst}</a></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
