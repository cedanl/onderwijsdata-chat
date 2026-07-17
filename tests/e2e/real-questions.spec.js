/**
 * Realistische vragen uit productie-chats, gescoord tegen ground truth.
 *
 * Leest evaluations.json voor verwachte datasets, tool-flow en datapunten.
 * Scoort elk model op: tool-efficiëntie, dataset-match, content-kwaliteit,
 * hallucinatie-risico.
 *
 * Run: TEST_MODELS=azure_ai/claude-haiku-4-5,openai/gpt-oss-120b npx playwright test real-questions
 */
import { test, expect } from 'playwright/test'
import { WebSocket } from 'ws'
import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const EVALS = JSON.parse(readFileSync(resolve(__dirname, 'evaluations.json'), 'utf-8')).evaluations

const API = 'http://localhost:8000'
const WS_URL = 'ws://localhost:8000/api/chat'
const MODELS = (process.env.TEST_MODELS || 'azure_ai/claude-haiku-4-5,openai/gpt-oss-120b').split(',').filter(Boolean)

function chat(token, message, model, timeoutMs = 300_000) {
  return new Promise((resolve) => {
    const ws = new WebSocket(`${WS_URL}?token=${token}`)
    const toolCalls = []
    const toolResults = []
    const textParts = []
    let resolved = false

    const finish = (extra = {}) => {
      if (resolved) return
      resolved = true
      clearTimeout(timer)
      try { ws.close() } catch {}
      resolve({ toolCalls, toolResults, content: textParts.join(''), ...extra })
    }
    const timer = setTimeout(() => finish({ timeout: true }), timeoutMs)

    ws.on('open', () => {
      ws.send(JSON.stringify({ action: 'settings', settings: { model } }))
      setTimeout(() => {
        ws.send(JSON.stringify({ action: 'message', content: message }))
      }, 200)
    })

    ws.on('message', (raw) => {
      try {
        const event = JSON.parse(raw.toString())
        if (event.type === 'tool_start') toolCalls.push(event.name)
        if (event.type === 'tool_end') toolResults.push({ name: event.name, output: (event.output || '').slice(0, 500) })
        if (event.type === 'text_delta') textParts.push(event.content)
        if (event.type === 'clarification') {
          const opties = event.opties || []
          const keuze = opties.find(o => o.aanbevolen) || opties[0]
          if (keuze) {
            console.log(`  CLARIFY: "${event.vraag}" → "${keuze.label}"`)
            setTimeout(() => ws.send(JSON.stringify({ action: 'clarification_choice', choice: keuze.label })), 500)
          } else {
            finish({ timeout: false })
          }
        }
        if (event.type === 'error') {
          console.log(`  ERROR: ${event.message}`)
          finish({ timeout: false, error: event.message })
        }
        if (event.type === 'message_end') finish({ timeout: false })
      } catch {}
    })

    ws.on('error', () => finish({ timeout: false }))
    ws.on('close', () => finish({ timeout: false }))
  })
}

function scoreResult(r, ev) {
  const scores = {}
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

  scores.total = total
  scores.max = maxPoints

  return scores
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
        const scores = scoreResult(r, ev)
        allScores[short] = scores

        console.log(`\n${'─'.repeat(60)}`)
        console.log(`[${short}] ${ev.label}`)
        console.log(`SCORE: ${scores.total}/${scores.max}`)
        console.log(`TOOLS (${r.toolCalls.length}): ${r.toolCalls.join(' → ') || '(geen)'}`)
        console.log(`search_catalog: ${scores.search_count}x (limiet: ${ev.expected.max_search_catalog || 3})`)
        console.log(`Verplichte tools: ${JSON.stringify(scores.required_tools)}`)
        console.log(`Dataset-match: ${scores.dataset_match} (${scores.datasets_found.join(', ') || 'geen'})`)
        console.log(`Content-match: ${JSON.stringify(scores.mentions)}`)
        if (scores.reference_checks) console.log(`Referentiewaarden: ${JSON.stringify(scores.reference_checks)}`)
        if (scores.has_percentage !== undefined) console.log(`Percentage: ${scores.has_percentage}`)
        if (scores.has_plot !== undefined) console.log(`Plot: ${scores.has_plot}`)
        console.log(`Hallucinatie-risico: ${scores.hallucination_risk}`)
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

      // Assertions per model
      for (const [modelName, scores] of Object.entries(allScores)) {
        expect(scores.hallucination_risk, `${modelName} geeft data-getallen zonder bronnen`).toBe(false)
        expect(scores.total, `${modelName} scoort te laag (${scores.total}/${scores.max})`).toBeGreaterThanOrEqual(30)
      }
    })
  }
})
