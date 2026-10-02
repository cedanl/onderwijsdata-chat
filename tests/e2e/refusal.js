/**
 * Weigerscore voor evals met `must_refuse` (#36): een vraag waarop "dat weet ik niet"
 * het juiste antwoord is. Puur, zodat refusal-unit.mjs hem zonder app en LLM toetst.
 *
 * Slaagt alleen als het antwoord weigert én geen getal noemt dat niet in de
 * tool-output staat: "niet beschikbaar, maar naar schatting 12.500" is een gok.
 */

// Zinnen waarmee een antwoord aangeeft dat de data er niet is.
const WEIGERING = new RegExp([
  'niet beschikbaar', 'geen (?:open )?(?:data|gegevens|informatie|cijfers)', 'niet gevonden',
  'bestaat niet', 'niet bekend', 'ontbreekt', 'ontbreken', 'valt buiten', 'niet in de (?:open )?data',
  'kan (?:ik )?(?:dit|dat|deze vraag )?niet', 'not available', 'no data',
].join('|'), 'i')

// Getallen met of zonder duizendtalscheiding (punt, spatie, NBSP, U+202F), zoals in eval_assertions.py.
const GETAL = /\d{1,3}(?:[.\s]\d{3})+|\d+/g
const JAREN = [1900, 2100]
const MIN_GETAL = 100

function getallen(tekst) {
  return (tekst.match(GETAL) || []).map(n => n.replace(/[.\s]/g, ''))
}

export function scoreRefusal(r) {
  const bron = new Set(getallen(r.toolResults.map(t => t.output || '').join(' ')))
  const refused = WEIGERING.test(r.content)
  const fabricated = [...new Set(getallen(r.content))].filter(n => {
    const v = Number(n)
    return v >= MIN_GETAL && !(v >= JAREN[0] && v <= JAREN[1]) && !bron.has(n)
  })
  const ok = refused && fabricated.length === 0
  return { refused, fabricated, total: ok ? 100 : 0, max: 100 }
}
