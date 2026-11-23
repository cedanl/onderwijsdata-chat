// A workbook as one standalone HTML file, to share with someone without an account (#254). A report already is
// one; the download inlines Plotly in it (offlineHtml.js). Generated dashboards are gone with the dashboard
// builder (#765), so a saved one never reaches the viewer or this download.

import { rapportdeel } from './bestandsnaam'

// The HTML of a workbook, or null for a built-in dashboard: that one is live app code.
export function workbookHtml(workbook) {
  if (workbook.builtin) return null
  return workbook.htmlContent || null
}

// De naam van de download, ook voor Markdown en Word: dezelfde regel als de server (bestandsnaam.js, #1124, #1125).
export const workbookFilename = workbook => `${rapportdeel(workbook.title)}.html`
