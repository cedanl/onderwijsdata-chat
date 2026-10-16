// "Vandaag", "Gisteren" or a short date for a conversation or report in a list. Locally-created timestamps
// are ms (Date.now()); the backend normalizes and returns them in seconds (persistence/db.py's
// _normalize_ts). Same > 1e12 heuristic as the backend uses, so either source renders correctly.
export function relatieveDatum(ts, nu = Date.now()) {
  const tsMs = ts > 1e12 ? ts : ts * 1000
  const days = Math.floor((nu - tsMs) / 86400000)
  if (days === 0) return 'Vandaag'
  if (days === 1) return 'Gisteren'
  return new Date(tsMs).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })
}
