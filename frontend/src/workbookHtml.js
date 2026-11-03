// A workbook as one standalone HTML file, to share with someone without an account (#254). A report already is
// one; the download inlines Plotly in it (offlineHtml.js). Generated dashboards are gone with the dashboard
// builder (#765), so a saved one never reaches the viewer or this download.

// The HTML of a workbook, or null for a built-in dashboard: that one is live app code.
export function workbookHtml(workbook) {
  if (workbook.builtin) return null
  return workbook.htmlContent || null
}

export const workbookFilename = workbook => (workbook.title || 'rapport').replace(/[^a-zA-Z0-9]/g, '_') + '.html'
