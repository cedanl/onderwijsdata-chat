/**
 * Realistische vragen uit productie-chats.
 *
 * Test diverse LLM-agent-vaardigheden:
 * - Trend-analyse (meerdere jaren, grafiek)
 * - Geo-analyse (regio, gemeente, provincie)
 * - Marktaandeel-berekening (run_analysis)
 * - Cross-bron-analyse (DUO + CBS/RIO)
 * - Concurrentie/overlap-analyse
 * - Arbeidsmarkt-koppeling (vacatures, aansluiting)
 *
 * Run: TEST_MODELS=azure_ai/claude-haiku-4-5,openai/gpt-oss-120b npx playwright test real-questions
 */
import { test, expect } from 'playwright/test'
import { WebSocket } from 'ws'

const API = 'http://localhost:8000'
const WS_URL = 'ws://localhost:8000/api/chat'
const MODELS = (process.env.TEST_MODELS || 'azure_ai/claude-haiku-4-5,openai/gpt-oss-120b').split(',').filter(Boolean)

const QUESTIONS = [
  {
    label: 'trend-analyse',
    message: 'Hoe heeft de deelname aan voltijdonderwijs bij Hogeschool Utrecht zich ontwikkeld de laatste 5 jaar? Geef het totaal.',
    expect_tools: ['search_catalog', 'get_duo_data'],
    check: (r) => {
      const hasPlot = r.toolCalls.includes('create_plot')
      const hasData = r.toolCalls.includes('query_data') || r.toolCalls.includes('get_duo_data')
      const hasYears = /202[0-5]/.test(r.content)
      return { hasPlot, hasData, hasYears }
    },
    description: 'Trend over meerdere jaren, moet grafiek opleveren',
  },
  {
    label: 'marktaandeel',
    message: 'Wat is het marktaandeel van ROC Mondriaan voor Sport en Bewegen in Zuid Holland? Geef instroom laatste schooljaar.',
    expect_tools: ['search_catalog'],
    check: (r) => {
      const hasAnalysis = r.toolCalls.includes('run_analysis') || r.toolCalls.includes('query_data')
      const hasPercentage = /%/.test(r.content) || /marktaandeel|aandeel/i.test(r.content)
      return { hasAnalysis, hasPercentage }
    },
    description: 'Marktaandeel-berekening met filtering op regio + opleiding',
  },
  {
    label: 'herkomst-concurrentie',
    message: 'Waar komen de lerenden van Hogeschool Utrecht vandaan en met welke instellingen in de regio concurreer ik? Geef per provincie.',
    expect_tools: ['search_catalog'],
    check: (r) => {
      const hasGeoData = /provincie|Utrecht|Noord-Holland|Zuid-Holland|Gelderland/i.test(r.content)
      const hasCompetitors = /hogeschool|universiteit|instelling/i.test(r.content)
      return { hasGeoData, hasCompetitors }
    },
    description: 'Geo-analyse met concurrentieperspectief',
  },
  {
    label: 'arbeidsmarkt-aansluiting',
    message: 'Sluit het onderwijsaanbod van Hogeschool Utrecht goed aan bij de arbeidsmarkt? Analyseer arbeidsmarktpositie van afgestudeerden de laatste 5 jaar per sector.',
    expect_tools: ['search_catalog'],
    check: (r) => {
      const hasCBS = r.toolCalls.includes('get_cbs_data') || /CBS|85776|85777/i.test(r.content)
      const hasSectors = /techniek|zorg|economie|sector|domein/i.test(r.content)
      return { hasCBS, hasSectors }
    },
    description: 'Cross-bron-analyse, arbeidsmarkt-data, sector-uitsplitsing',
  },
  {
    label: 'vsv-regio',
    message: 'Hoe groot is het aandeel voortijdig schoolverlaters dat werk heeft gevonden in de regio Utrecht? Geef het meest recente jaar.',
    expect_tools: ['search_catalog'],
    check: (r) => {
      const hasVSV = /vsv|voortijdig|schoolverlat/i.test(r.content)
      const hasPercentage = /%|aandeel|percentage/i.test(r.content)
      return { hasVSV, hasPercentage }
    },
    description: 'Niche-dataset (VSV), regiofilter, percentage-berekening',
  },
]

async function getToken() {
  const resp = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'admin' }),
  })
  return (await resp.json()).token
}

function chat(token, message, model, timeoutMs = 180_000) {
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

test.describe('Productie-vragen', () => {
  let token
  test.beforeAll(async () => { token = await getToken() })

  for (const q of QUESTIONS) {
    test(`${q.label}: ${q.description}`, async () => {
      test.setTimeout(300_000)
      const results = {}

      for (const model of MODELS) {
        const short = model.split('/').pop()
        const r = await chat(token, q.message, model)
        results[short] = r

        const checks = q.check(r)

        console.log(`\n${'─'.repeat(60)}`)
        console.log(`[${short}] ${q.label}`)
        console.log(`TOOLS: ${r.toolCalls.join(' → ') || '(geen)'}`)
        console.log(`CHECKS: ${JSON.stringify(checks)}`)
        console.log(`ANTWOORD (400 chars):\n${r.content.slice(0, 400)}`)
        if (r.error) console.log(`ERROR: ${r.error}`)
        if (r.timeout) console.log(`TIMEOUT!`)
        console.log('─'.repeat(60))
      }

      // Vergelijk
      const modelNames = Object.keys(results)
      if (modelNames.length === 2) {
        const [a, b] = modelNames
        const ra = results[a], rb = results[b]

        console.log(`\n${'═'.repeat(60)}`)
        console.log(`VERGELIJKING — ${q.label}`)
        console.log(`${a} tools (${ra.toolCalls.length}): ${ra.toolCalls.join(' → ') || '(geen)'}`)
        console.log(`${b} tools (${rb.toolCalls.length}): ${rb.toolCalls.join(' → ') || '(geen)'}`)

        // Check getallen overlap
        const numsA = [...new Set((ra.content.match(/\b\d[\d.]*\b/g) || []).filter(n => parseFloat(n) > 100))]
        const numsB = [...new Set((rb.content.match(/\b\d[\d.]*\b/g) || []).filter(n => parseFloat(n) > 100))]
        const overlap = numsA.filter(n => numsB.includes(n))
        console.log(`${a} getallen >100: ${numsA.slice(0, 8).join(', ') || '(geen)'}`)
        console.log(`${b} getallen >100: ${numsB.slice(0, 8).join(', ') || '(geen)'}`)
        console.log(`Overlap getallen: ${overlap.join(', ') || '(geen)'}`)

        // Hallucinatie-check
        const dataToolsA = ra.toolCalls.filter(t => ['get_duo_data','get_cbs_data','query_data','run_analysis'].includes(t))
        const dataToolsB = rb.toolCalls.filter(t => ['get_duo_data','get_cbs_data','query_data','run_analysis'].includes(t))
        const hallA = dataToolsA.length === 0 && numsA.length > 2
        const hallB = dataToolsB.length === 0 && numsB.length > 2
        console.log(`${a} hallucinatie-risico: ${hallA}`)
        console.log(`${b} hallucinatie-risico: ${hallB}`)
        console.log('═'.repeat(60))

        if (!ra.error) expect(hallA, `${a} geeft data-getallen zonder bronnen`).toBe(false)
        if (!rb.error) expect(hallB, `${b} geeft data-getallen zonder bronnen`).toBe(false)
      }

      // Basis-check: minstens één model moet search_catalog hebben aangeroepen
      const anySearched = Object.values(results).some(r => r.toolCalls.includes('search_catalog'))
      const anyError = Object.values(results).some(r => r.error)
      if (!anyError) {
        expect(anySearched, 'Geen enkel model heeft search_catalog aangeroepen').toBe(true)
      }
    })
  }
})
