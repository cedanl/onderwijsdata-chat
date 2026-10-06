import { useState } from 'react'
import { workbookHtml, workbookFilename } from '../dashboardHtml'
import { inlinePlotly } from '../offlineHtml'
import { saveFile } from '../saveFile'

// A report or generated dashboard as one HTML file that opens without the app or a network (#254, #405).
export default function WorkbookDownload({ workbook, instelling, save = saveFile }) {
  const [error, setError] = useState(null)
  if (workbook.builtin) return null

  async function download() {
    setError(null)
    try {
      const html = await inlinePlotly(await workbookHtml(workbook, { instelling }))
      if (!html) throw new Error('Dit dashboard heeft geen inhoud om te downloaden.')
      save(new Blob([html], { type: 'text/html;charset=utf-8' }), workbookFilename(workbook))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
      <button type="button" className="wb-download-btn" onClick={download}>Download als HTML</button>
      {error && <span className="wb-download-error" role="alert">{error}</span>}
    </>
  )
}
