/**
 * De rapporteval (#752): volgt een rapport de bijsturing uit het gesprek? Puur, zodat rapport-unit.mjs het zonder
 * app en zonder LLM toetst. De controles lezen wat code vastlegde (de bronregel en de reeksen van elke grafiek, de
 * onderzoeksvraag), niet wat het model erover schreef.
 */
import { onderzoeksvraagVoorstel } from '../../frontend/src/onderzoeksvraagVoorstel.js'

/** Het gesprek zoals de app het bij "Genereer rapport" kent: vragen en antwoorden, een afgebroken antwoord gemarkeerd. */
export function berichten(beurten) {
  return beurten.flatMap(({ vraag, antwoord }) => [
    { role: 'user', content: vraag },
    {
      role: 'assistant',
      content: antwoord.content || '',
      ...(antwoord.einde !== 'geldig' && { stopped: true }),
      ...(antwoord.error && { isError: true }),
    },
  ])
}

/** De onderzoeksvraag die de app voorstelt (#751), met dezelfde functie als de app. */
export function voorstel(beurten) {
  return onderzoeksvraagVoorstel(berichten(beurten))
}

function figuur(vis) {
  const ruw = vis?.figure_json
  if (typeof ruw !== 'string') return ruw && typeof ruw === 'object' ? ruw : {}
  try { return JSON.parse(ruw) } catch { return {} }
}

/** De labels van een grafiek: reeksnamen, en categorieën op de assen of in een taart. */
export function reekslabels(vis) {
  const labels = []
  for (const trace of figuur(vis).data || []) {
    if (typeof trace.name === 'string') labels.push(trace.name)
    for (const as of ['x', 'y', 'labels']) {
      for (const waarde of Array.isArray(trace[as]) ? trace[as] : []) if (typeof waarde === 'string') labels.push(waarde)
    }
  }
  return [...new Set(labels)]
}

/** De bronregel van een grafiek als één tekst: de regel zelf, de dataset en de link (agent/figuurbron.py). */
function bronregel(vis) {
  const bron = vis?.bron
  return bron ? [bron.tekst, bron.dataset, bron.url].filter(Boolean).join(' ') : ''
}

const patroon = p => new RegExp(p, 'i')
const normaal = tekst => String(tekst || '').replace(/\s+/g, ' ').trim()

/**
 * De fouten van één rapport tegen de verwachting van een scenario; leeg is geslaagd.
 *
 * verwachting: min_visualisaties, onderzoeksvraag_is_voorstel, onderzoeksvraag_noemt / _niet,
 * bron_wel (een grafiek), bron_niet (geen grafiek) en reeksen_niet (geen label in een grafiek); patronen
 * zijn regexen zonder hoofdlettergevoeligheid, zoals must_mention in evaluations.json.
 */
export function rapportFouten(uitkomst, verwachting, voorgesteld) {
  if (uitkomst.timeout) return ['rapport: time-out']
  if (uitkomst.error) return [`rapport: ${uitkomst.error}`]
  const spec = uitkomst.spec
  if (!spec) return ['rapport: geen spec']
  const fouten = []
  const visualisaties = spec.visualisaties || []
  const vraag = normaal(spec.onderzoeksvraag)

  if (visualisaties.length < (verwachting.min_visualisaties ?? 1)) {
    fouten.push(`${visualisaties.length} grafieken, verwacht ten minste ${verwachting.min_visualisaties ?? 1}`)
  }
  if (verwachting.onderzoeksvraag_is_voorstel && vraag !== normaal(voorgesteld)) {
    fouten.push(`onderzoeksvraag is niet de bevestigde: "${vraag}" in plaats van "${normaal(voorgesteld)}"`)
  }
  for (const p of verwachting.onderzoeksvraag_noemt || []) {
    if (!patroon(p).test(vraag)) fouten.push(`onderzoeksvraag noemt /${p}/ niet: "${vraag}"`)
  }
  for (const p of verwachting.onderzoeksvraag_niet || []) {
    if (patroon(p).test(vraag)) fouten.push(`onderzoeksvraag noemt /${p}/: "${vraag}"`)
  }
  for (const p of verwachting.bron_wel || []) {
    if (!visualisaties.some(v => patroon(p).test(bronregel(v)))) fouten.push(`geen grafiek met bron /${p}/`)
  }
  visualisaties.forEach((vis, i) => {
    const naam = `grafiek ${i + 1} ("${vis.titel || ''}")`
    for (const p of verwachting.bron_niet || []) {
      if (patroon(p).test(bronregel(vis))) fouten.push(`${naam}: bron /${p}/: ${bronregel(vis)}`)
    }
    for (const p of verwachting.reeksen_niet || []) {
      const geraakt = reekslabels(vis).filter(label => patroon(p).test(label))
      if (geraakt.length) fouten.push(`${naam}: reeks /${p}/: ${geraakt.join(', ')}`)
    }
  })
  return fouten
}

/** De fouten van de beurten zelf: een rapport over een mislukt gesprek zegt niets. */
export function gesprekFouten(beurten) {
  return beurten.flatMap(({ vraag, antwoord }, i) => {
    const kop = `beurt ${i + 1} ("${vraag.slice(0, 40)}")`
    if (antwoord.timeout) return [`${kop}: time-out`]
    if (antwoord.error) return [`${kop}: ${antwoord.error}`]
    if (antwoord.einde !== 'geldig') return [`${kop}: einde ${antwoord.einde ?? 'ontbreekt'}`]
    return []
  })
}

/** Per scenario hoeveel runs slaagden, met de fouten per mislukte run (voor eval_results/). */
export function rapportVerslag(runs, { gemeten_op = new Date().toISOString().slice(0, 10), herhalingen = 1 } = {}) {
  const scenarios = {}
  for (const { scenario, model, fouten } of runs) {
    const cel = (scenarios[scenario] ??= { runs: 0, geslaagd: 0, mislukt: [] })
    cel.runs += 1
    if (fouten.length) cel.mislukt.push({ model, fouten })
    else cel.geslaagd += 1
  }
  return { gemeten_op, herhalingen, scenarios }
}
