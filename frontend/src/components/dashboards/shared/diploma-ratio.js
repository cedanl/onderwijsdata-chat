// De ratio diploma/inschrijving deelt gediplomeerden en ingeschrevenen van hetzelfde jaar (#927). Bij hbo/wo publiceert
// DUO de gediplomeerden een jaar later dan de ingeschrevenen; wie het laatste jaar van elke reeks neemt, deelt 2024 door
// 2025 en laat dat niet zien. Eén regel voor de KPI, de eigen instelling en elke peer.

const heeftWaarde = (reeks, jaar) => reeks?.[jaar] != null

// Het laatste jaar waarin beide reeksen een waarde hebben en er ingeschreven studenten zijn; null als dat niet bestaat.
export function ratioJaar(gediplomeerden, ingeschrevenen) {
  if (!gediplomeerden || !ingeschrevenen) return null
  const jaren = Object.keys(gediplomeerden)
    .filter(jaar => heeftWaarde(gediplomeerden, jaar) && ingeschrevenen[jaar] > 0)
    .sort((a, b) => b - a)
  return jaren[0] ?? null
}

// Het percentage in één jaar, afgerond; null als een van de twee ontbreekt in dat jaar.
export function ratioPercentage(gediplomeerden, ingeschrevenen, jaar) {
  if (!heeftWaarde(gediplomeerden, jaar) || !(ingeschrevenen?.[jaar] > 0)) return null
  return Math.round(gediplomeerden[jaar] / ingeschrevenen[jaar] * 100)
}

// De ratio van de eigen instelling in haar laatste gemeenschappelijke jaar: { jaar, procent }, of null.
export function diplomaRatio(data) {
  const jaar = ratioJaar(data?.gediplomeerden, data?.ingeschrevenen)
  return jaar == null ? null : { jaar, procent: ratioPercentage(data.gediplomeerden, data.ingeschrevenen, jaar) }
}
