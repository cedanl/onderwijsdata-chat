/**
 * Rapporteval (#752): volgt een rapport de bijsturing uit het gesprek? Per scenario een gesprek over één
 * verbinding (rapportscenarios.json), dan "Genereer rapport" met de onderzoeksvraag die de app voorstelt (#751),
 * en de controles uit code op de spec die terugkomt (rapportscore.js).
 *
 * Run: EVAL_BASE_URL=… EVAL_USERNAME=… EVAL_PASSWORD=… TEST_MODELS=azure_ai/claude-sonnet-5-5 TEST_REPEATS=3 \
 *   npx playwright test rapport-bijsturing --config=playwright.eval.config.js
 * Per scenario het aantal geslaagde runs, met de reden van elke mislukte, gaat naar eval_results/rapport-<datum>.json.
 */
import { test, expect } from 'playwright/test'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'url'
import { haalToken } from './chatstream.js'
import { RAPPORT_TIMEOUT_MS, VRAAG_TIMEOUT_MS, verbind } from './gesprek.js'
import { gesprekFouten, rapportFouten, rapportVerslag, reekslabels, voorstel } from './rapportscore.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SCENARIOS = JSON.parse(readFileSync(resolve(__dirname, 'rapportscenarios.json'), 'utf-8')).scenarios
const MODELS = (process.env.TEST_MODELS || 'azure_ai/claude-sonnet-5-5').split(',').filter(Boolean)
const REPEATS = Math.max(1, Number(process.env.TEST_REPEATS) || 1)
const RESULTATEN = resolve(__dirname, '..', '..', 'eval_results')
const RUNS = []

async function speel(token, scenario, model) {
  const gesprek = await verbind(token, model)
  try {
    const beurten = []
    for (const vraag of scenario.berichten) {
      beurten.push({ vraag, antwoord: await gesprek.vraag(vraag) })
      if (gesprekFouten(beurten).length) return { beurten, fouten: gesprekFouten(beurten) }
    }
    const voorgesteld = voorstel(beurten)
    const uitkomst = await gesprek.rapport({ onderzoeksvraag: voorgesteld })
    return { beurten, voorgesteld, uitkomst, fouten: rapportFouten(uitkomst, scenario.verwachting, voorgesteld) }
  } finally {
    gesprek.sluit()
  }
}

test.describe('Rapport volgt de bijsturing (evaluatie)', () => {
  let token
  test.beforeAll(async () => { token = await haalToken() })
  test.afterAll(() => {
    mkdirSync(RESULTATEN, { recursive: true })
    const verslag = rapportVerslag(RUNS, { herhalingen: REPEATS })
    writeFileSync(resolve(RESULTATEN, `rapport-${verslag.gemeten_op}.json`), JSON.stringify(verslag, null, 2) + '\n')
  })

  for (const scenario of SCENARIOS) {
    test(`${scenario.label}: ${scenario.description}`, async () => {
      const perRun = scenario.berichten.length * VRAAG_TIMEOUT_MS + RAPPORT_TIMEOUT_MS
      test.setTimeout(perRun * MODELS.length * REPEATS)
      const mislukt = []

      for (const model of MODELS) for (let beurt = 1; beurt <= REPEATS; beurt++) {
        const kort = REPEATS > 1 ? `${model.split('/').pop()}#${beurt}` : model.split('/').pop()
        const r = await speel(token, scenario, model)
        RUNS.push({ scenario: scenario.label, model: kort, fouten: r.fouten })
        if (r.fouten.length) mislukt.push(`${kort}: ${r.fouten.join('; ')}`)

        console.log(`\n${'─'.repeat(60)}`)
        console.log(`[${kort}] ${scenario.label}`)
        for (const { vraag, antwoord } of r.beurten) {
          console.log(`VRAAG: ${vraag}`)
          console.log(`  TOOLS: ${antwoord.toolCalls.join(' → ') || '(geen)'}`)
          console.log(`  ANTWOORD (300 chars): ${(antwoord.content || '').slice(0, 300)}`)
        }
        if (r.voorgesteld !== undefined) console.log(`VOORGESTELDE ONDERZOEKSVRAAG: ${r.voorgesteld}`)
        const spec = r.uitkomst?.spec
        if (spec) {
          console.log(`RAPPORT: "${spec.title}"; onderzoeksvraag: ${spec.onderzoeksvraag}`)
          for (const vis of spec.visualisaties || []) {
            console.log(`  GRAFIEK "${vis.titel}": ${vis.bron?.tekst || '(bron onbekend)'}`)
            console.log(`    reeksen: ${reekslabels(vis).slice(0, 12).join(', ')}`)
          }
        }
        console.log(`UITKOMST: ${r.fouten.length ? `niet geslaagd: ${r.fouten.join('; ')}` : 'geslaagd'}`)
        console.log('─'.repeat(60))
      }

      expect(mislukt, `${scenario.label}: niet elke run volgde de bijsturing`).toEqual([])
    })
  }
})
