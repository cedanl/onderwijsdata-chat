import RunProgress from './RunProgress'

export const REPORT_SLOW_NOTE = 'Dit duurt langer dan normaal. Je kunt blijven wachten of het rapport annuleren.'

// The wait for a report: time, steps and what the run does now, and a way out (#339).
// After the last step the model writes the report for minutes without a new step: the note
// says that is expected (#417). Past REPORT_SLOW_MS (`slow`) it says the wait is longer than normal (#1050);
// the note is a polite status region that is there from the start, so the change is announced.
export default function ReportProgress({ busy, progress, slow = false, onCancel }) {
  if (!busy) return null
  return (
    <div className="report-progress">
      <div className="report-progress-row">
        <RunProgress busy={busy} steps={progress.steps} stepLabel={progress.label} />
        <button type="button" className="report-cancel-btn" onClick={onCancel}>Annuleer</button>
      </div>
      <p className="report-progress-note" role="status">
        {slow ? REPORT_SLOW_NOTE : 'Een rapport maken duurt meestal een paar minuten.'}
      </p>
    </div>
  )
}
