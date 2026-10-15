// The tables behind an answer: what query_data, run_analysis and get_maat left in the store (#269).
// The server only names a table for a step that delivered rows; the status check
// keeps a step that was later marked empty or failed out of the export.
import { citatieRijen } from './citatieCsv'

export function exportKeys(tools) {
  const keys = (tools || []).filter(t => t.exportKey && !t.status).map(t => t.exportKey)
  return [...new Set(keys)]
}

// Whether a data answer has something to download (#544): the tables of its steps when the
// server named one, else the numbers it cites. The cited numbers exist for every answer that
// read data, so the button no longer depends on which tool the model chose (#191).
export function hasExport(msg) {
  return exportKeys(msg?.tools).length > 0 || citatieRijen(msg?.citaties).length > 0
}

// Whether the model round behind messages[i] is over. The server ends only the last
// round with message_end, so an earlier round that wrote text and ran the data steps
// keeps done=false (#399). It is over once a later message exists or nothing runs.
export function roundSettled(messages, i, busy) {
  return !!messages[i].done || !busy || i < messages.length - 1
}
