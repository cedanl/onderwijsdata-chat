/* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */
import { useEffect, useState } from 'react'
import { fetchCatalogCounts } from '../api'
import { useDialog } from '../hooks/useDialog'

// Counts come from the catalog the app searches, so they cannot drift from it.
const withCount = (n, text) => (n ? `${n} ${text}` : text)

export default function DataSourcesModal({ onClose }) {
  const [counts, setCounts] = useState({})
  const dialogRef = useDialog(onClose)
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
              <tr><th>Bron</th><th>Inhoud</th><th>Catalogus</th></tr>
            </thead>
            <tbody>
              {[
                ['CBS', withCount(counts.CBS, 'datasets met onderwijsstatistieken'), 'cedanl.github.io/cbs-onderwijsdata', 'https://cedanl.github.io/cbs-onderwijsdata'],
                ['RIO', `Register van onderwijsinstellingen en opleidingen${counts.RIO ? ` (${counts.RIO} resources)` : ''}`, 'cedanl.github.io/rio-onderwijsdata', 'https://cedanl.github.io/rio-onderwijsdata'],
                ['DUO', withCount(counts.DUO, 'open datasets: prognoses, diplomering, instroom, adressen'), 'onderwijsdata.duo.nl', 'https://onderwijsdata.duo.nl'],
              ].map(([bron, inhoud, catalogus, href]) => (
                <tr key={bron}>
                  <td><span className="source-name">{bron}</span></td>
                  <td><span className="source-desc">{inhoud}</span></td>
                  <td><a href={href} target="_blank" rel="noreferrer">{catalogus}</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
