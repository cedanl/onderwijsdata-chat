import { workbookFilename } from '../dashboardHtml'
import { kanMarkdown, rapportUitHtml } from '../rapportUitHtml'
import { rapportMarkdown } from '../rapportMarkdown'
import { saveFile } from '../saveFile'

// "Download als Markdown" (#746): de tekst van een rapport om in een eigen document aan te vullen, naast de
// HTML-download en "Opslaan als PDF". Alleen voor een rapport; het HTML-document wordt pas bij de klik gelezen.
export default function WorkbookMarkdown({ workbook, save = saveFile }) {
  const html = workbook.htmlContent
  if (workbook.dashboardSpec || !kanMarkdown(html)) return null

  function download() {
    const markdown = rapportMarkdown(rapportUitHtml(html))
    save(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }), workbookFilename(workbook).replace(/\.html$/, '.md'))
  }

  return <button type="button" className="wb-download-btn" onClick={download}>Download als Markdown</button>
}
