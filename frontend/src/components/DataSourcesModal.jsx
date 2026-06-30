export default function DataSourcesModal({ onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <button className="modal-overlay-close" onClick={onClose}>
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
                ['CBS', '68 datasets met onderwijsstatistieken', 'cedanl.github.io/cbs-onderwijsdata', 'https://cedanl.github.io/cbs-onderwijsdata'],
                ['RIO', 'Register van onderwijsinstellingen en opleidingen (14 resources)', 'cedanl.github.io/rio-onderwijsdata', 'https://cedanl.github.io/rio-onderwijsdata'],
                ['DUO', '57 open datasets: prognoses, diplomering, instroom, adressen', 'onderwijsdata.duo.nl', 'https://onderwijsdata.duo.nl'],
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
