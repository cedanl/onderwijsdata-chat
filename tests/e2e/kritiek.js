/**
 * De kritieke set van de bronwaarheid-evals en haar drempel (besluit #693, #753). Puur, zodat score-unit.mjs het
 * zonder app en zonder LLM toetst.
 *
 * De evals blokkeren niets: de checklist voor de promotie leest de uitslag (`docs/promoten.md`). Kritiek zijn de
 * vragen met `expected.kritiek`: de ijk-cases met exacte bronwaarden (#190), de weigeringen en het #742-paar
 * (geslacht per opleiding). Een weigering moet in elke run slagen, want een verzonnen getal is de ernstige fout;
 * een andere kritieke vraag in een meerderheid van de runs (2 van 3). Een kritieke vraag zonder run telt als niet
 * gehaald: stilte is geen succes.
 */

export const isKritiek = ev => ev?.expected?.kritiek === true

/** Hoeveel van `herhalingen` runs moeten slagen. */
export function drempel(ev, herhalingen) {
  return ev?.expected?.must_refuse ? herhalingen : Math.floor(herhalingen / 2) + 1
}

/** De redenen waarom één run niet slaagde; leeg is geslaagd. Dezelfde eisen als de assertions van de runner. */
export function foutenVan(ev, scores) {
  const poorten = Object.entries(scores.poorten || {}).filter(([, ok]) => !ok).map(([naam]) => `poort: ${naam}`)
  if (!ev.expected.must_refuse) return [...new Set([...poorten, ...(scores.fouten || [])])]
  return [
    ...poorten,
    ...(scores.refused ? [] : ['weigert niet']),
    ...(scores.fabricated?.length ? [`verzonnen getallen: ${scores.fabricated.join(', ')}`] : []),
  ]
}

export function nieuweStand() {
  return {}
}

/** Eén run van een kritieke vraag erbij; een andere vraag telt hier niet. */
export function voegRunToe(stand, model, ev, fouten) {
  if (!isKritiek(ev)) return stand
  const cel = ((stand[model] ??= {})[ev.label] ??= { runs: 0, geslaagd: 0, mislukt: [] })
  cel.runs += 1
  if (fouten.length) cel.mislukt.push({ run: cel.runs, fouten })
  else cel.geslaagd += 1
  return stand
}

/** Per model elke kritieke vraag met haar drempel en of die gehaald is, plus wat rood is. */
export function kritiekVerslag(stand, evals, { gemeten_op = new Date().toISOString().slice(0, 10), herhalingen = 1 } = {}) {
  const kritiek = evals.filter(isKritiek)
  const modellen = {}
  for (const model of Object.keys(stand).length ? Object.keys(stand) : ['(geen run)']) {
    const vragen = {}
    for (const ev of kritiek) {
      const cel = stand[model]?.[ev.label] ?? { runs: 0, geslaagd: 0, mislukt: [] }
      const nodig = drempel(ev, herhalingen)
      vragen[ev.label] = {
        ...cel,
        drempel: nodig,
        gehaald: cel.runs > 0 && cel.geslaagd >= nodig,
        ...(cel.runs === 0 && { reden: 'niet gedraaid' }),
      }
    }
    const rood = Object.entries(vragen).filter(([, v]) => !v.gehaald).map(([label]) => label)
    modellen[model] = { gehaald: kritiek.length - rood.length, totaal: kritiek.length, rood, vragen }
  }
  return { gemeten_op, herhalingen, modellen }
}

/** Eén regel per model voor de joblog en de promotie-MR: "kritiek: 14 van 15 gehaald; rood: ijk-hu-deeltijd (1/3)". */
export function samenvatting(verslag) {
  return Object.entries(verslag.modellen).map(([model, m]) => {
    const rood = m.rood.map(label => {
      const v = m.vragen[label]
      return v.runs ? `${label} (${v.geslaagd}/${v.runs})` : `${label} (niet gedraaid)`
    })
    return `kritiek ${model}: ${m.gehaald} van ${m.totaal} gehaald; ${rood.length ? `rood: ${rood.join(', ')}` : 'niets rood'}`
  })
}
