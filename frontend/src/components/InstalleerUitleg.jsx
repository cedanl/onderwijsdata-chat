/* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */
import { useDialog } from '../hooks/useDialog'

// iOS geeft geen installatieprompt (#671): zonder deze stappen weet een docent niet dat het kan.
export default function InstalleerUitleg({ onClose }) {
  const dialogRef = useDialog(onClose)
  return (
    <div className="modal-overlay" ref={dialogRef} onClick={onClose} role="dialog" aria-modal="true" aria-label="Zet op je startscherm" tabIndex={-1}>
      <button type="button" className="modal-overlay-close" onClick={onClose} aria-label="Sluiten">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 20, height: 20 }}>
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header"><h2>Zet op je startscherm</h2></div>
        <div className="modal-body installeer-uitleg">
          <p>Dan opent openEDUdata+ schermvullend, met een eigen icoon.</p>
          <ol className="installeer-stappen">
            <li>Tik onderin op <strong>Delen</strong> (het vierkant met een pijl omhoog).</li>
            <li>Kies <strong>Zet op beginscherm</strong>.</li>
            <li>Laat <strong>Open als web-app</strong> aan.</li>
            <li>Tik op <strong>Voeg toe</strong>.</li>
          </ol>
        </div>
      </div>
    </div>
  )
}
