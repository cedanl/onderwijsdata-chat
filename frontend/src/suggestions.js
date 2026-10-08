import { SUGGESTED, SECTOREN } from './constants'

// Suggested questions are written in the first person ("ons", "mijn regio"); with an
// institution in the profile they name it instead.
export function personalizeQuestion(q, instelling) {
  if (!instelling) return q
  return q
    .replaceAll('ons onderwijsaanbod', `het aanbod van ${instelling}`)
    .replaceAll('onze instelling', instelling)
    .replaceAll('mijn lerenden', `de lerenden van ${instelling}`)
    .replaceAll('mijn regio', `de regio van ${instelling}`)
    .replaceAll('mijn provincie', `de provincie van ${instelling}`)
    .replaceAll('bij ons', `bij ${instelling}`)
}

// The suggested questions the sources can answer for an institution of this sector (#447).
// Unknown sector: only the questions that hold for every sector.
export function suggestionsFor(sector, categories = SUGGESTED) {
  const holds = q => (sector ? q.sectoren.includes(sector) : SECTOREN.every(s => q.sectoren.includes(s)))
  return categories.map(({ category, questions }) => ({ category, questions: questions.filter(holds).map(q => q.tekst) }))
}
