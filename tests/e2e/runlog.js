/**
 * De uitslag van elke eval-run op schijf, en de verslagen daaruit na de hele run (#753).
 *
 * Playwright start na een mislukte test een nieuwe worker. Een stand in het geheugen van de spec raakte dan kwijt,
 * en `afterAll` schreef per worker een verslag met alleen de laatste vragen: het slagingspercentage, het rapportverslag
 * (#752) en de kritieke set misten zo juist de runs die faalden. Nu legt elke run één regel vast in
 * `eval_results/runs.jsonl`; `eval-setup.js` wist dat bestand vóór de run en `eval-teardown.js` bouwt de verslagen na
 * alle workers. `verslagen` is puur, zodat score-unit.mjs het zonder app en zonder LLM toetst.
 */
import { appendFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { kritiekVerslag, nieuweStand, samenvatting, voegRunToe } from './kritiek.js'
import { nieuweMatrix, rapport, voegToe } from './matrix.js'
import { rapportVerslag } from './rapportscore.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
export const RESULTATEN = resolve(__dirname, '..', '..', 'eval_results')
const RUNS = resolve(RESULTATEN, 'runs.jsonl')

/** Eén run: { soort: 'vraag', model, label, fouten } of { soort: 'rapport', scenario, model, fouten }. */
export function legVast(run) {
  mkdirSync(RESULTATEN, { recursive: true })
  appendFileSync(RUNS, JSON.stringify(run) + '\n')
}

export function wisRuns() {
  rmSync(RUNS, { force: true })
}

export function leesRuns() {
  if (!existsSync(RUNS)) return []
  return readFileSync(RUNS, 'utf-8').split('\n').filter(Boolean).map(regel => JSON.parse(regel))
}

/** De verslagen uit de runs; een soort zonder runs geeft geen verslag. */
export function verslagen(runs, evals, { herhalingen = 1, gemeten_op = new Date().toISOString().slice(0, 10) } = {}) {
  const uit = {}
  const vragen = runs.filter(r => r.soort === 'vraag')
  if (vragen.length) {
    const matrix = nieuweMatrix()
    const stand = nieuweStand()
    const perLabel = Object.fromEntries(evals.map(ev => [ev.label, ev]))
    for (const r of vragen) {
      voegToe(matrix, r.model, r.label, r.fouten.length === 0)
      if (perLabel[r.label]) voegRunToe(stand, r.model, perLabel[r.label], r.fouten)
    }
    uit.slagingspercentage = rapport(matrix, { herhalingen, gemeten_op })
    uit.kritiek = kritiekVerslag(stand, evals, { herhalingen, gemeten_op })
  }
  const rapporten = runs.filter(r => r.soort === 'rapport')
  if (rapporten.length) uit.rapport = rapportVerslag(rapporten, { herhalingen, gemeten_op })
  return uit
}

/** Schrijf elk verslag als eval_results/<soort>-<datum>.json; de regels van de kritieke set gaan naar de log. */
export function schrijfVerslagen(evals, opties = {}) {
  const alle = verslagen(leesRuns(), evals, opties)
  mkdirSync(RESULTATEN, { recursive: true })
  for (const [soort, verslag] of Object.entries(alle)) {
    writeFileSync(resolve(RESULTATEN, `${soort}-${verslag.gemeten_op}.json`), JSON.stringify(verslag, null, 2) + '\n')
  }
  return alle.kritiek ? samenvatting(alle.kritiek) : []
}
