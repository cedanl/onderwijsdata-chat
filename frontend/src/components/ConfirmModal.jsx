import { useId } from 'react'
import { useDialog } from '../hooks/useDialog'

export default function ConfirmModal({ message, confirmLabel = 'Verwijderen', onConfirm, onCancel }) {
  const dialogRef = useDialog(onCancel)
  const messageId = useId()
  return (
    <div className="confirm-overlay">
      <div className="confirm-dialog" ref={dialogRef} role="alertdialog" aria-modal="true" aria-describedby={messageId} tabIndex={-1}>
        <p className="confirm-message" id={messageId}>{message}</p>
        <div className="confirm-actions">
          <button type="button" className="confirm-cancel" onClick={onCancel}>Annuleren</button>
          <button type="button" className="confirm-destructive" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}
