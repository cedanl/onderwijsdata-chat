import RunProgress from './RunProgress'

// The wait for a report: time, steps and what the run does now, and a way out (#339).
export default function ReportProgress({ busy, progress, onCancel }) {
  if (!busy) return null
  return (
    <div className="report-progress">
      <RunProgress busy={busy} steps={progress.steps} stepLabel={progress.label} />
      <button type="button" className="report-cancel-btn" onClick={onCancel}>Annuleer</button>
    </div>
  )
}
