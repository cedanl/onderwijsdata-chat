import { useState } from 'react'
import { downloadRapportDocx } from '../api'
import { workbookFilename } from '../workbookHtml'
import { kanMarkdown, rapportUitHtml } from '../rapportUitHtml'
import { grafiekFormulier, vraagGrafieken } from '../rapportGrafieken'
import { saveFile } from '../saveFile'

export const ZONDER_ALLE_GRAFIEKEN = 'Het Word-document is gedownload, maar niet elke grafiek kon mee. Daar staat "Grafiek niet beschikbaar".'

// "Download als Word" (#1038): het rapport als bewerkbaar .docx in Npuls-huisstijl, om aan te vullen met eigen
// bevindingen. De server maakt het document uit het bewaarde rapport; de browser stuurt alleen de grafieken als PNG
// mee (rapportGrafieken.js). `grafiekDoc` is het rapport voor het grafiekframe (useReportFrame), of null als het
// rapport niet in een frame te zien is: dan gaan er geen grafieken mee. Mislukken alleen de grafieken, dan komt het
// document toch, met een melding. Alleen voor een rapport, zoals "Download als Markdown".
export default function WorkbookWord({ workbook, grafiekDoc = null, save = saveFile, vraag = vraagGrafieken, verstuur = downloadRapportDocx }) {
  const [bezig, setBezig] = useState(false)
  const [melding, setMelding] = useState(null)
  const html = workbook.htmlContent
  if (workbook.builtin || !kanMarkdown(html)) return null

  async function maakDocument(form) {
    try {
      return { blob: await verstuur(workbook.id, form), zonder: false }
    } catch (e) {
      // Weigert de server de grafieken (te groot, geen PNG), dan het document zonder grafieken.
      if (![400, 413].includes(e.status) || ![...form.keys()].length) throw e
      return { blob: await verstuur(workbook.id, new FormData()), zonder: true }
    }
  }

  async function download() {
    if (bezig) return
    setBezig(true)
    setMelding(null)
    try {
      const grafieken = grafiekDoc ? await vraag(grafiekDoc).catch(() => []) : []
      const { form, mee } = grafiekFormulier(grafieken)
      const { blob, zonder } = await maakDocument(form)
      save(blob, workbookFilename(workbook).replace(/\.html$/, '.docx'))
      const aantal = rapportUitHtml(html).visualisaties.length
      if (zonder || mee < aantal) setMelding({ fout: false, tekst: ZONDER_ALLE_GRAFIEKEN })
    } catch (e) {
      setMelding({ fout: true, tekst: `Het Word-document kon niet worden gemaakt: ${e.message}` })
    } finally {
      setBezig(false)
    }
  }

  return (
    <>
      <button type="button" className="wb-download-btn" onClick={download} aria-disabled={bezig || undefined} aria-busy={bezig || undefined}>
        {bezig ? 'Word-document maken…' : 'Download als Word'}
      </button>
      {melding && (
        <span className={melding.fout ? 'wb-download-error' : 'wb-download-notice'} role={melding.fout ? 'alert' : 'status'}>
          {melding.tekst}
        </span>
      )}
    </>
  )
}
