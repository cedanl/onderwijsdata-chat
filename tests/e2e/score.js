/**
 * Score voor de productievragen uit evaluations.json (#360, CH-28). Puur, zodat score-unit.mjs
 * hem zonder app en zonder LLM toetst.
 *
 * Eerst de poorten uit chatstream.js (geldig einde, tekst, geen fout, geen timeout): faalt er
 * één, dan is de score 0. Daarna valt elke eis apart te benoemen in `fouten`: verplichte tool,
 * dataset, term, referentiewaarde, grafiek, percentage. Vóór CH-28 haalde een leeg antwoord met
 * 'Authentication rejected' 40 of 60 punten bij een grens van 30.
 */
import { poorten } from './chatstream.js'

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

  // 6. Data-referentiewaarden controleren
  if (ex.data_points?.reference_values) {
    const tolerance = (ex.data_points.tolerance_pct || 10) / 100
    scores.reference_checks = {}
    for (const [key, expected] of Object.entries(ex.data_points.reference_values)) {
      const numPattern = new RegExp(`${expected.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1[. ]?')}`, 'g')
      const found = numPattern.test(r.content) || numPattern.test(allText)
      if (!found) {
        // probeer met tolerantie: zoek getallen in de buurt
        const nums = (r.content.match(/[\d.]+/g) || []).map(n => parseFloat(n.replace(/\./g, '')))
        const close = nums.some(n => Math.abs(n - expected) / expected <= tolerance)
        scores.reference_checks[key] = close ? 'close' : 'missing'
      } else {
        scores.reference_checks[key] = 'exact'
      }
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

  // 10. Acceptable outcomes (als gedefinieerd)
  if (ex.acceptable_outcomes) {
    scores.acceptable_outcome = ex.acceptable_outcomes.some(outcome => {
      const keywords = outcome.toLowerCase().split(/\s+/).filter(w => w.length > 4)
      const matchCount = keywords.filter(k => r.content.toLowerCase().includes(k)).length
      return matchCount >= Math.ceil(keywords.length * 0.3)
    })
  }

  // Totaalscore (0-100)
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

  scores.fouten = fouten(scores, allDatasets.length > 0)
  // Een leeg, mislukt of afgebroken resultaat scoort niets, hoe zuinig het ook zocht.
  scores.total = Object.values(scores.poorten).every(Boolean) ? total : 0
  scores.max = maxPoints

  return scores
}

/** Elke eis die faalt, apart benoemd; een zachte totaalscore mag er geen verbergen. */
function fouten(scores, datasetsVerwacht) {
  const uit = Object.entries(scores.poorten).filter(([, ok]) => !ok).map(([naam]) => `poort: ${naam}`)
  if (uit.length) return uit
  if (scores.hallucination_risk) uit.push('getallen zonder datatool')
  // Een vooraf aanvaarde andere uitkomst ("niet per instelling beschikbaar") vervangt de data-eisen.
  if (scores.acceptable_outcome) return uit
  for (const [tool, ok] of Object.entries(scores.required_tools)) if (!ok) uit.push(`tool ontbreekt: ${tool}`)
  if (datasetsVerwacht && !scores.dataset_match) uit.push('verwachte dataset niet gebruikt')
  for (const [term, ok] of Object.entries(scores.mentions)) if (!ok) uit.push(`term ontbreekt: ${term}`)
  for (const [k, v] of Object.entries(scores.reference_checks || {})) if (v === 'missing') uit.push(`referentiewaarde ontbreekt: ${k}`)
  if (scores.has_plot === false) uit.push('grafiek ontbreekt')
  if (scores.has_percentage === false) uit.push('percentage ontbreekt')
  return uit
}
