import { useState } from 'react'
import { workbookHtml, workbookFilename } from '../workbookHtml'
import { inlinePlotly } from '../offlineHtml'
import { metCsp } from '../rapportSandbox'
import { saveFile } from '../saveFile'

// A report as one HTML file that opens without the app or a network (#254, #405).
// Shared by the button in the viewer bar and the notice under a report that does not show (#541). Opened from
// disk it has no sandbox, so it carries the report policy (#634): its scripts run, but reach nothing.
export function useWorkbookDownload(workbook, save = saveFile) {
  const [error, setError] = useState(null)

  async function download() {
    setError(null)
    try {
      const html = metCsp(await inlinePlotly(workbookHtml(workbook)))
      if (!html) throw new Error('Dit rapport heeft geen inhoud om te downloaden.')
      save(new Blob([html], { type: 'text/html;charset=utf-8' }), workbookFilename(workbook))
    } catch (e) {
      setError(e.message)
    }
  }

  return { download, error }
}

export default function WorkbookDownload({ workbook, save }) {
  const { download, error } = useWorkbookDownload(workbook, save)
  if (workbook.builtin) return null

  return (
    <>
      <button type="button" className="wb-download-btn" onClick={download}>Download als HTML</button>
      {error && <span className="wb-download-error" role="alert">{error}</span>}
    </>
  )
}
