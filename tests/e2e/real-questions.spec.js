/**
 * Realistische vragen uit productie-chats, gescoord tegen ground truth.
 *
 * Leest evaluations.json voor verwachte datasets, tool-flow en datapunten.
 * Scoort elk model op: tool-efficiëntie, dataset-match, content-kwaliteit,
 * hallucinatie-risico (score.js). Een leeg, mislukt of afgebroken antwoord faalt altijd,
 * en elke eis faalt apart (CH-28). Het token gaat als WS-subprotocol mee (chatstream.js).
 *
 * Run: TEST_MODELS=azure_ai/claude-haiku-4-5,openai/gpt-oss-120b npx playwright test real-questions
 */
import { test, expect } from 'playwright/test'
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'url'
import { scoreRefusal } from './refusal.js'
import { scoreResult } from './score.js'
import { WebSocket } from 'ws'
import { WS_URL, nieuwAntwoord, poorten, protocollen, verwerk } from './chatstream.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const EVALS = JSON.parse(readFileSync(resolve(__dirname, 'evaluations.json'), 'utf-8')).evaluations

const API = 'http://localhost:8000'
const MODELS = (process.env.TEST_MODELS || 'azure_ai/claude-haiku-4-5,openai/gpt-oss-120b').split(',').filter(Boolean)

// Na een message_end kan nog een verduidelijkingsvraag volgen (agent/run.py sluit eerst de
// lopende tekst af); pas als die uitblijft, is het antwoord af.
const NA_EINDE_MS = 1_000

function chat(token, message, model, timeoutMs = 300_000) {
  return new Promise((resolve) => {
    const ws = new WebSocket(WS_URL, protocollen(token))
    const antwoord = nieuwAntwoord()
    let resolved = false
    let naEinde = null

    const finish = (extra = {}) => {
      if (resolved) return
      resolved = true
      clearTimeout(timer)
      clearTimeout(naEinde)
      try { ws.close() } catch {}
      resolve({ ...antwoord, ...extra })
    }
    const timer = setTimeout(() => finish({ timeout: true }), timeoutMs)

    ws.on('open', () => {
      ws.send(JSON.stringify({ action: 'settings', settings: { model } }))
      setTimeout(() => {
        ws.send(JSON.stringify({ action: 'message', content: message }))
      }, 200)
    })

    ws.on('message', (raw) => {
      let event
      try { event = JSON.parse(raw.toString()) } catch { return }
      verwerk(antwoord, event)
      if (event.type === 'clarification') {
        clearTimeout(naEinde)
        antwoord.einde = null
        const opties = event.opties || []
        const keuze = opties.find(o => o.aanbevolen) || opties[0]
        if (!keuze) return finish()
        console.log(`  CLARIFY: "${event.vraag}" → "${keuze.label}"`)
        setTimeout(() => ws.send(JSON.stringify({ action: 'clarification_choice', choice: keuze.label })), 500)
      }
      if (event.type === 'error') {
        console.log(`  ERROR: ${event.message}`)
        finish()
      }
      if (event.type === 'message_end') {
        clearTimeout(naEinde)
        naEinde = setTimeout(() => finish(), NA_EINDE_MS)
      }
    })

    // Een weigering bij de handshake (4001) of een verbroken verbinding is een fout, geen leeg succes.
    ws.on('error', (err) => finish({ error: antwoord.error || `verbinding: ${err.message}` }))
    ws.on('close', (code) => finish(antwoord.einde ? {} : { error: antwoord.error || `verbinding gesloten (${code})` }))
  })
}

async function getToken() {
  const resp = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'admin' }),
  })
  return (await resp.json()).token
}

test.describe('Productie-vragen (evaluatie)', () => {
  let token
  test.beforeAll(async () => { token = await getToken() })

  for (const ev of EVALS) {
    test(`${ev.label}: ${ev.description}`, async () => {
      test.setTimeout(300_000)
      const allScores = {}

      for (const model of MODELS) {
        const short = model.split('/').pop()
        const r = await chat(token, ev.message, model)
        const scores = ev.expected.must_refuse ? { ...scoreRefusal(r), poorten: poorten(r) } : scoreResult(r, ev)
        allScores[short] = scores

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
