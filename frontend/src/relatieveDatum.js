// "Vandaag", "Gisteren" or a short date for a conversation or report in a list. Locally-created timestamps
// are ms (Date.now()); the backend normalizes and returns them in seconds (persistence/db.py's
// _normalize_ts). Same > 1e12 heuristic as the backend uses, so either source renders correctly.
const naarMs = ts => (ts > 1e12 ? ts : ts * 1000)

// Calendar days in local time, so last night at 23:50 is "Gisteren" at 10:00. Rounded: a day with a
// daylight-saving switch lasts 23 or 25 hours.
const middernacht = ms => new Date(ms).setHours(0, 0, 0, 0)

export function relatieveDatum(ts, nu = Date.now()) {
  const tsMs = naarMs(ts)
  const days = Math.round((middernacht(nu) - middernacht(tsMs)) / 86400000)
  if (days === 0) return 'Vandaag'
  if (days === 1) return 'Gisteren'
  return new Date(tsMs).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })
}

// The same with the local time, "Vandaag 14:32": two conversations of one day with the same title are then told
// apart (#654).
export function relatieveDatumTijd(ts, nu = Date.now()) {
  const tijd = new Date(naarMs(ts)).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' })
  return `${relatieveDatum(ts, nu)} ${tijd}`
}
