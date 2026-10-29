/**
 * Realistische vragen uit productie-chats, gescoord tegen ground truth.
 *
 * Leest evaluations.json voor verwachte datasets, tool-flow en datapunten.
 * Scoort elk model op: tool-efficiëntie, dataset-match, content-kwaliteit,
 * hallucinatie-risico (score.js). Een leeg, mislukt of afgebroken antwoord faalt altijd,
 * en elke eis faalt apart (CH-28). Het token gaat als WS-subprotocol mee (chatstream.js).
 *
 * Run: TEST_MODELS=azure_ai/claude-haiku-4-5,openai/gpt-oss-120b npx playwright test real-questions
 * Herhaling: TEST_REPEATS=3 laat elke vraag drie keer per model lopen; één fout telt (#190). Het
 * slagingspercentage per model en vraag gaat als JSON naar eval_results/slagingspercentage-<datum>.json, de kritieke
 * set met haar drempel (besluit #693) naar eval_results/kritiek-<datum>.json, met één regel per model in de log
 * ("kritiek …: 14 van 15 gehaald; rood: …"); eval-teardown.js schrijft ze uit de runs van alle workers (runlog.js).
 */
import { test, expect } from 'playwright/test'
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'url'
import { scoreRefusal } from './refusal.js'
import { scoreResult } from './score.js'
import { laadIjkwaarden, metIjkwaarden } from './ijkwaarden.js'
import { foutenVan } from './kritiek.js'
import { legVast } from './runlog.js'
import { haalToken, poorten } from './chatstream.js'
import { losseVraag } from './gesprek.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
// De referentiewaarden van een bronwaarheid-case komen uit ijkwaarden.json, niet uit de eval zelf (#190).
const IJK = laadIjkwaarden()
const EVALS = JSON.parse(readFileSync(resolve(__dirname, 'evaluations.json'), 'utf-8')).evaluations.map(ev => metIjkwaarden(ev, IJK))

const MODELS = (process.env.TEST_MODELS || 'azure_ai/claude-haiku-4-5,openai/gpt-oss-120b').split(',').filter(Boolean)
const REPEATS = Math.max(1, Number(process.env.TEST_REPEATS) || 1)

test.describe('Productie-vragen (evaluatie)', () => {
  let token
  test.beforeAll(async () => { token = await haalToken() })

  for (const ev of EVALS) {
    test(`${ev.label}: ${ev.description}`, async () => {
      test.setTimeout(300_000 * MODELS.length * REPEATS)
      const allScores = {}

      for (const model of MODELS) for (let beurt = 1; beurt <= REPEATS; beurt++) {
        const short = REPEATS > 1 ? `${model.split('/').pop()}#${beurt}` : model.split('/').pop()
        const r = await losseVraag(token, ev.message, model)
        const scores = ev.expected.must_refuse ? { ...scoreRefusal(r), poorten: poorten(r) } : scoreResult(r, ev)
        allScores[short] = scores
        // Op schijf, niet in het geheugen: na een mislukte test begint een nieuwe worker (#753).
        legVast({ soort: 'vraag', model, label: ev.label, fouten: foutenVan(ev, scores) })

        console.log(`\n${'─'.repeat(60)}`)
        console.log(`[${short}] ${ev.label}`)
        console.log(`SCORE: ${scores.total}/${scores.max}`)
        console.log(`Poorten: ${JSON.stringify(scores.poorten)}; ingetrokken versies: ${r.ingetrokken}`)
        if (ev.expected.foutcategorie) console.log(`Foutcategorie bij falen: ${ev.expected.foutcategorie} (bron: ${ev.expected.bron_versie})`)
        if (ev.expected.must_refuse) {
          console.log(`Weigert: ${scores.refused}; verzonnen getallen: ${scores.fabricated.join(', ') || 'geen'}`)
          console.log(`ANTWOORD (400 chars):\n${r.content.slice(0, 400)}`)
          continue
        }
        console.log(`TOOLS (${r.toolCalls.length}): ${r.toolCalls.join(' → ') || '(geen)'}`)
        console.log(`search_catalog: ${scores.search_count}x (limiet: ${ev.expected.max_search_catalog || 3})`)
        console.log(`Verplichte tools: ${JSON.stringify(scores.required_tools)}`)
        console.log(`Dataset-match: ${scores.dataset_match} (${scores.datasets_found.join(', ') || 'geen'})`)
        console.log(`Content-match: ${JSON.stringify(scores.mentions)}`)
        if (scores.reference_checks) console.log(`Referentiewaarden: ${JSON.stringify(scores.reference_checks)}`)
        if (scores.bron_gevonden) console.log(`Bron gevonden: ${JSON.stringify(scores.bron_gevonden)}`)
        console.log(`Uitkomst: ${scores.uitkomst}${scores.uitkomst_id ? ` (${scores.uitkomst_id})` : ''}`)
        if (scores.has_percentage !== undefined) console.log(`Percentage: ${scores.has_percentage}`)
        if (scores.has_plot !== undefined) console.log(`Plot: ${scores.has_plot}`)
        console.log(`Hallucinatie-risico: ${scores.hallucination_risk}`)
        console.log(`Fouten: ${scores.fouten.join('; ') || 'geen'}`)
        if (r.timeout) console.log(`TIMEOUT!`)
        console.log(`ANTWOORD (400 chars):\n${r.content.slice(0, 400)}`)
        console.log('─'.repeat(60))
      }

      // Vergelijking als er meerdere modellen zijn
      const modelNames = Object.keys(allScores)
      if (modelNames.length >= 2) {
        console.log(`\n${'═'.repeat(60)}`)
        console.log(`SCORECARD — ${ev.label}`)
        for (const m of modelNames) {
          const s = allScores[m]
          console.log(`  ${m.padEnd(20)} ${s.total}/${s.max} punten`)
        }
        console.log('═'.repeat(60))
      }

      // Assertions per model; een audit-case noemt de schakel die faalt (#360)
      const categorie = ev.expected.foutcategorie ? ` [${ev.expected.foutcategorie}]` : ''
      for (const [modelName, scores] of Object.entries(allScores)) {
        // Een leeg, mislukt of afgebroken antwoord is nooit goed, ook niet als weigering (CH-28).
        expect(scores.poorten, `${modelName} gaf geen geldig antwoord${categorie}`).toEqual({
          geldig_einde: true, tekst: true, geen_fout: true, geen_timeout: true,
        })
        if (ev.expected.must_refuse) {
          // Integraal weigeren: geen gok, ook niet naast een weigerzin (#36).
          expect(scores.fabricated, `${modelName} noemt getallen zonder bron`).toEqual([])
          expect(scores.refused, `${modelName} weigert niet`).toBe(true)
          continue
        }
        // Elke eis apart: referentiewaarde, dataset, tools, termen; geen zachte totaalscore (CH-28).
        expect(scores.fouten, `${modelName} haalt niet alle eisen${categorie}`).toEqual([])
      }
    })
  }
})
