import { useId } from 'react'
import { useDialog } from '../hooks/useDialog'

// cancelLabel: "Annuleren" kan ook "breek het af" lijken; bij weggaan tijdens een run heet die knop "Blijven" (#772).
export default function ConfirmModal({ message, confirmLabel = 'Verwijderen', cancelLabel = 'Annuleren', onConfirm, onCancel }) {
  const dialogRef = useDialog(onCancel)
  const messageId = useId()
  return (
    <div className="confirm-overlay">
      <div className="confirm-dialog" ref={dialogRef} role="alertdialog" aria-modal="true" aria-describedby={messageId} tabIndex={-1}>
        <p className="confirm-message" id={messageId}>{message}</p>
        <div className="confirm-actions">
          <button type="button" className="confirm-cancel" onClick={onCancel}>{cancelLabel}</button>
          <button type="button" className="confirm-destructive" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}
