// A reasoning step once its tool_end arrives. The server reads the outcome from the tool
// result (#386): status 'empty' or 'error' with its own label; no status means it delivered.
// exportKey: the table this step left in the store, for the CSV download (#269).
export function finishStep(step, ev) {
  const done = { ...step, done: true, snippet: ev.snippet || null, exportKey: ev.export_key || null }
  if (!ev.status) return done
  return { ...done, status: ev.status, statusLabel: ev.status_label, suggesties: ev.suggesties || null }
}
