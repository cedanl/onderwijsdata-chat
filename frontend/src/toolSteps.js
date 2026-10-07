// A reasoning step once its tool_end arrives. The server reads the outcome from the tool
// result (#386): status 'empty' or 'error' with its own label; no status means it delivered.
// exportKey: the table this step left in the store, for the CSV download (#269).
export function finishStep(step, ev) {
  const done = { ...step, done: true, snippet: ev.snippet || null, exportKey: ev.export_key || null }
  if (!ev.status) return done
  return { ...done, status: ev.status, statusLabel: ev.status_label, suggesties: ev.suggesties || null }
}

// A failed or empty step that a later run of the same tool made good (#426): the app
// recovered by itself, so the card says so instead of leaving a bare "Filter mislukt".
export function markRecovered(steps) {
  return steps.map((step, i) => {
    if (!step.done || !step.status) return step
    const later = steps.slice(i + 1).some(s => s.name === step.name && s.done && !s.status)
    return later ? { ...step, recovered: true } : step
  })
}
