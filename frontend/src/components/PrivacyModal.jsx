/* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */
import { createPortal } from 'react-dom'
import { useDialog } from '../hooks/useDialog'
import PrivacyInhoud from './PrivacyInhoud'

// The privacy information as a popup (#572), with the same text as the /privacy page. No API calls, so it
// also works before login. Rendered into <body>: opened from the settings dialog, its backdrop click must
// not reach the settings backdrop, and it stacks above that dialog.
export default function PrivacyModal({ onClose }) {
  const dialogRef = useDialog(onClose)
  const closeFromBackdrop = e => {
    // A portal's click still bubbles through the React tree to every host: stop it here, do not rely on the host.
    e.stopPropagation()
    onClose()
  }

  return createPortal(
    <div className="modal-overlay modal-overlay--privacy" ref={dialogRef} onClick={closeFromBackdrop} role="dialog" aria-modal="true" aria-label="Privacy-informatie" tabIndex={-1}>
      <div className="modal modal--privacy" onClick={e => e.stopPropagation()}>
        {/* Sticky, so the close button stays in reach while the long text scrolls. */}
        <div className="privacy-modal-bar">
          <button type="button" className="modal-close" onClick={onClose} aria-label="Sluiten">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 18, height: 18 }}>
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <PrivacyInhoud />
      </div>
    </div>,
    document.body,
  )
}
