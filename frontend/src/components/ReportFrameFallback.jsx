import { useWorkbookDownload } from './WorkbookDownload'

// Outside the report frame, whose content the page cannot see (#541): when the frame says it shows nothing or
// gives no sign of life, a question with the download. The status container is always there, so the live region
// exists before it fills. It sits above the report, not over it, in case the frame does show something.
export default function ReportFrameFallback({ probleem, workbook, instelling, save }) {
  const { download, error } = useWorkbookDownload(workbook, instelling, save)

  return (
    <>
      <div className="wb-viewer-fallback-status" role="status">
        {probleem && (
          <p className="wb-viewer-fallback">
            Zie je dit rapport niet?{' '}
            <button type="button" className="wb-viewer-fallback-link" onClick={download}>Download het als HTML</button>.
          </p>
        )}
      </div>
      {probleem && error && <p className="wb-download-error wb-viewer-fallback-error" role="alert">{error}</p>}
    </>
  )
}
