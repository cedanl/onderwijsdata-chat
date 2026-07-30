export default function ConfirmModal({ message, confirmLabel = 'Verwijderen', onConfirm, onCancel }) {
  return (
    <div className="confirm-overlay">
      <div className="confirm-dialog">
        <p className="confirm-message">{message}</p>
        <div className="confirm-actions">
          <button type="button" className="confirm-cancel" onClick={onCancel}>Annuleren</button>
          <button type="button" className="confirm-destructive" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}
