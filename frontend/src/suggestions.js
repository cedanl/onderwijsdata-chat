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

// The question for this sector: `{variant}` takes the sector's text, `standaard` when unknown (CH-43).
function tekstVoor(q, sector) {
  return q.varianten ? q.tekst.replace('{variant}', q.varianten[sector ?? 'standaard']) : q.tekst
}

// The suggested questions the sources can answer for an institution of this sector (#447).
// Unknown sector: only the questions that hold for every sector. Without an institution in the
// profile, only the questions that need none (CH-42); an empty category is left out.
export function suggestionsFor(sector, { profiel = true } = {}, categories = SUGGESTED) {
  const holds = q =>
    (sector ? q.sectoren.includes(sector) : SECTOREN.every(s => q.sectoren.includes(s))) &&
    (q.profiel === undefined || q.profiel === profiel)
  return categories
    .map(({ category, questions }) => ({ category, questions: questions.filter(holds).map(q => tekstVoor(q, sector)) }))
    .filter(c => c.questions.length > 0)
}
