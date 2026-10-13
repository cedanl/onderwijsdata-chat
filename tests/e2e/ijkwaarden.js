/**
 * IJkwaarden in de evals (#190). Puur, zodat score-unit.mjs het zonder app en zonder LLM toetst.
 *
 * Een eval verwijst per sleutel naar een id in ijkwaarden.json (`data_points.ijkwaarden`); de
 * waarde zelf staat alleen daar, rechtstreeks bij de bron opgehaald door scripts/ijkwaarden.py.
 * Hier wordt de verwijzing een `reference_values`-tabel zoals score.js die leest. Een ijkwaarde
 * is exact: geen tolerantie, want 7.408 of 7.418 is het verschil tussen goed en fout.
 */
import { readFileSync } from 'node:fs'

export function laadIjkwaarden(url = new URL('./ijkwaarden.json', import.meta.url)) {
  return JSON.parse(readFileSync(url, 'utf-8')).waarden
}

/** De eval met `reference_values` uit de fixture; zonder verwijzingen ongewijzigd. */
export function metIjkwaarden(ev, waarden) {
  const verwijzingen = ev.expected?.data_points?.ijkwaarden
  if (!verwijzingen) return ev
  const referenties = {}
  for (const [sleutel, id] of Object.entries(verwijzingen)) {
    const ijk = waarden[id]
    if (!ijk || typeof ijk.waarde !== 'number') throw new Error(`${ev.label}: ijkwaarde ${id} ontbreekt of is geen getal`)
    referenties[sleutel] = ijk.waarde
  }
  const data_points = { ...ev.expected.data_points, reference_values: referenties, tolerance_pct: 0 }
  return { ...ev, expected: { ...ev.expected, data_points } }
}
