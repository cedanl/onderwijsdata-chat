import RunProgress from './RunProgress'

// The wait for a report: time, steps and what the run does now, and a way out (#339).
// After the last step the model writes the report for minutes without a new step: the note
// says that is expected (#417).
export default function ReportProgress({ busy, progress, onCancel }) {
  if (!busy) return null
  return (
    <div className="report-progress">
      <div className="report-progress-row">
        <RunProgress busy={busy} steps={progress.steps} stepLabel={progress.label} />
        <button type="button" className="report-cancel-btn" onClick={onCancel}>Annuleer</button>
      </div>
      <p className="report-progress-note">Een rapport maken duurt meestal een paar minuten.</p>
    </div>
  )
}
