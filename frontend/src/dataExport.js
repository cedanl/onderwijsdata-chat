// The tables behind an answer: what query_data and run_analysis left in the store (#269).
// The server only names a table for a step that delivered rows; the status check
// keeps a step that was later marked empty or failed out of the export.
export function exportKeys(tools) {
  const keys = (tools || []).filter(t => t.exportKey && !t.status).map(t => t.exportKey)
  return [...new Set(keys)]
}
