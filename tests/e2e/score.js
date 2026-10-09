/**
 * Score voor de productievragen uit evaluations.json (#360, CH-28). Puur, zodat score-unit.mjs
 * hem zonder app en zonder LLM toetst.
 *
 * Eerst de poorten uit chatstream.js (geldig einde, tekst, geen fout, geen timeout): faalt er
 * één, dan is de score 0. Daarna valt elke eis apart te benoemen in `fouten`: verplichte tool,
 * dataset, term, referentiewaarde, bron, grafiek, percentage. Vóór CH-28 haalde een leeg antwoord met
 * 'Authentication rejected' 40 of 60 punten bij een grens van 30.
 *
 * Een referentiewaarde telt alleen als het eindantwoord haar bij haar jaar (en instelling, maat)
 * noemt; dat de tooluitvoer haar bevat, is een aparte uitkomst (#463, antwoord.js).
 */
import { poorten } from './chatstream.js'
import { tegenspreekt, waardeInAntwoord, waardeInBron } from './antwoord.js'

export function scoreResult(r, ev) {
  const scores = { poorten: poorten(r) }
  const ex = ev.expected

  // 1. Tool-efficiëntie: search_catalog binnen limiet?
  const searchCount = r.toolCalls.filter(t => t === 'search_catalog').length
  const maxSearch = ex.max_search_catalog || 3
  scores.search_within_limit = searchCount <= maxSearch
  scores.search_count = searchCount
  scores.total_tools = r.toolCalls.length

  // 2. Verplichte tools aanwezig?
  scores.required_tools = {}
  for (const tool of (ex.must_contain_tools || [])) {
    scores.required_tools[tool] = r.toolCalls.includes(tool)
  }
  scores.has_all_required = Object.values(scores.required_tools).every(Boolean)

  // 3. Dataset-match: worden verwachte datasets genoemd in antwoord of tool output?
  const allText = r.content + ' ' + r.toolResults.map(t => t.output).join(' ')
  const allDatasets = [...(ex.datasets || []), ...(ex.datasets_alt || [])]
  const datasetIds = allDatasets.map(d => d.split(':')[1]).filter(Boolean)
  scores.datasets_found = datasetIds.filter(id => {
    const pattern = new RegExp(id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i')
    return pattern.test(allText)
  })
  scores.dataset_match = scores.datasets_found.length > 0

  // 4. Content-kwaliteit: verplichte termen aanwezig?
  scores.mentions = {}
  for (const term of (ex.must_mention || [])) {
    scores.mentions[term] = new RegExp(term, 'i').test(r.content)
  }
  scores.has_all_mentions = Object.values(scores.mentions).every(Boolean)

  // 5. Plot aanwezig als verwacht?
  if (ex.must_have_plot) {
    scores.has_plot = r.toolCalls.includes('create_plot')
  }

  // 6. Referentiewaarden: het eindantwoord bewijst de waarde (antwoordcorrectheid), de
  //    tooluitvoer los daarvan dat de bron haar gaf (bronophaalcorrectheid).
  const dp = ex.data_points
  if (dp?.reference_values) {
    const tolerantie = (dp.tolerance_pct ?? 10) / 100
    const sleutels = Object.keys(dp.reference_values)
    const toolOutputs = r.toolResults.map(t => t.output)
    scores.reference_checks = {}
    scores.bron_gevonden = {}
    for (const [sleutel, verwacht] of Object.entries(dp.reference_values)) {
      const anderen = sleutels.filter(s => s !== sleutel).map(s => dp.reference_values[s])
      const context = { sleutel, sleutels, verwacht, anderen, entiteit: dp.entity, maat: dp.maat, tolerantie }
      scores.reference_checks[sleutel] = waardeInAntwoord(r.content, context)
      scores.bron_gevonden[sleutel] = waardeInBron(toolOutputs, verwacht)
    }
  }

  // 7. Percentage aanwezig als verwacht?
  if (ex.data_points?.must_be_percentage) {
    scores.has_percentage = /%/.test(r.content) || /marktaandeel|aandeel|percentage/i.test(r.content)
  }

  // 8. Hallucinatie-risico
  const dataTools = r.toolCalls.filter(t => ['get_duo_data', 'get_cbs_data', 'query_data', 'run_analysis'].includes(t))
  const nums = [...new Set((r.content.match(/\b\d[\d.]*\b/g) || []).filter(n => parseFloat(n) > 100))]
  scores.hallucination_risk = dataTools.length === 0 && nums.length > 2

  // 9. Timeout
  scores.timeout = !!r.timeout

  // 10. Uitkomst: 'data' als elke data-eis gehaald is, 'beperking' als het antwoord een vooraf
  //     vastgelegde andere uitkomst geeft, anders 'geen'.
  const dataFouten = dataEisFouten(scores, allDatasets.length > 0)
  scores.uitkomst_id = dataFouten.length ? aanvaardeUitkomst(r.content, ex) : null
  scores.uitkomst = !dataFouten.length ? 'data' : scores.uitkomst_id ? 'beperking' : 'geen'

  // Totaalscore (0-100): de behaalde punten naar rato van de te behalen punten
  let total = 0, maxPoints = 0

  // Zoek-efficiëntie (20 punten)
  maxPoints += 20
  if (scores.search_within_limit) total += 20
  else if (searchCount <= maxSearch + 2) total += 10

  // Verplichte tools (20 punten)
  maxPoints += 20
  if (scores.has_all_required) total += 20
  else {
    const found = Object.values(scores.required_tools).filter(Boolean).length
    const needed = Object.keys(scores.required_tools).length
    if (needed > 0) total += Math.round(20 * found / needed)
  }

  // Dataset-match (20 punten)
  maxPoints += 20
  if (scores.dataset_match) total += 20

  // Content-kwaliteit (20 punten)
  maxPoints += 20
  if (scores.has_all_mentions) total += 20
  else {
    const found = Object.values(scores.mentions).filter(Boolean).length
    const needed = Object.keys(scores.mentions).length
    if (needed > 0) total += Math.round(20 * found / needed)
  }

  // Geen hallucinatie (10 punten)
  maxPoints += 10
  if (!scores.hallucination_risk) total += 10

  // Geen timeout (10 punten)
  maxPoints += 10
  if (!scores.timeout) total += 10

  // Antwoordcorrectheid (20 punten): elke referentiewaarde exact in het eindantwoord
  const checks = Object.values(scores.reference_checks || {})
  if (checks.length) {
    maxPoints += 20
    total += Math.round(20 * checks.filter(c => c === 'exact').length / checks.length)
  }

  scores.fouten = fouten(scores, dataFouten)
  // Een leeg, mislukt of afgebroken resultaat scoort niets, hoe zuinig het ook zocht.
  scores.total = Object.values(scores.poorten).every(Boolean) ? Math.round(100 * total / maxPoints) : 0
  scores.max = 100

  return scores
}

/** Elke eis die faalt, apart benoemd; een zachte totaalscore mag er geen verbergen. */
function fouten(scores, dataFouten) {
  const uit = Object.entries(scores.poorten).filter(([, ok]) => !ok).map(([naam]) => `poort: ${naam}`)
  if (uit.length) return uit
  if (scores.hallucination_risk) uit.push('getallen zonder datatool')
  // Een vooraf vastgelegde andere uitkomst ("niet per instelling beschikbaar") vervangt de data-eisen.
  if (scores.uitkomst === 'beperking') return uit
  return [...uit, ...dataFouten]
}

/** De data-eisen die falen. 'close' is geen bewijs: alleen 'exact' haalt een referentiewaarde. */
function dataEisFouten(scores, datasetsVerwacht) {
  const uit = []
  for (const [tool, ok] of Object.entries(scores.required_tools)) if (!ok) uit.push(`tool ontbreekt: ${tool}`)
  if (datasetsVerwacht && !scores.dataset_match) uit.push('verwachte dataset niet gebruikt')
  for (const [term, ok] of Object.entries(scores.mentions)) if (!ok) uit.push(`term ontbreekt: ${term}`)
  for (const [k, v] of Object.entries(scores.reference_checks || {})) {
    if (v !== 'exact') uit.push(`referentiewaarde ontbreekt: ${k}`)
  }
  for (const [k, ok] of Object.entries(scores.bron_gevonden || {})) {
    if (!ok) uit.push(`bron: waarde niet in tooluitvoer: ${k}`)
  }
  if (scores.has_plot === false) uit.push('grafiek ontbreekt')
  if (scores.has_percentage === false) uit.push('percentage ontbreekt')
  return uit
}

/**
 * De id van de vastgelegde andere uitkomst die het antwoord geeft, of null. Elke marker moet
 * erin staan (hoofdletterongevoelige regex, zoals must_mention), en het antwoord mag bij geen
 * referentiewaarde een ander getal noemen.
 */
function aanvaardeUitkomst(content, ex) {
  if (tegenspreekt(content, ex.data_points)) return null
  const passend = (ex.acceptable_outcomes || []).find(u =>
    u.markers?.length && u.markers.every(m => new RegExp(m, 'i').test(content)))
  return passend?.id ?? null
}
