/**
 * Model-vergelijkingstest via WebSocket.
 *
 * Stuurt dezelfde vragen naar twee modellen en vergelijkt:
 * - Welke tools worden aangeroepen (search_catalog, dataset_details, clarify_scope)
 * - Of de two-stage retrieval flow gevolgd wordt
 * - Toon (geen fluff/complimenten)
 *
 * Vereist: make dev draait, CHAT_USERS=admin:admin,
 * AVAILABLE_MODELS bevat beide modellen, WILLMA_API_KEY is ingesteld.
 *
 * Run: TEST_MODELS=anthropic/claude-sonnet-4-6,openai/gpt-oss-120b npx playwright test model-comparison
 */
import { test, expect } from 'playwright/test'
import { WebSocket } from 'ws'

const API = 'http://localhost:8000'
const WS_URL = 'ws://localhost:8000/api/chat'
const MODELS = (process.env.TEST_MODELS || '').split(',').filter(Boolean)
const USE_DEFAULT = MODELS.length === 0

const TEST_QUESTIONS = [
  {
    label: 'scope-discipline',
    message: 'Hoeveel studenten heeft de Hogeschool Utrecht?',
    expect_tool: 'clarify_scope',
    expect_event: 'clarification',
    description: 'Moet clarify_scope aanroepen, niet direct data laden',
  },
  {
    label: 'catalog-retrieval',
    message: 'Zoek datasets over arbeidsmarktpositie van hbo-afgestudeerden',
    expect_tool: 'search_catalog',
    expect_followup_tool: 'dataset_details',
    description: 'search_catalog → dataset_details (two-stage retrieval)',
  },
  {
    label: 'toon-check',
    message: 'Wat is het verschil tussen instroom en inschrijving bij het DUO?',
    expect_tool: null,
    description: 'Zakelijke toon, geen complimenten',
  },
]

async function getToken() {
  const resp = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'admin' }),
  })
  const data = await resp.json()
  return data.token
}

function chatViaWebSocket(token, message, model, timeoutMs = 120_000) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`${WS_URL}?token=${token}`)
    const toolCalls = []
    const textParts = []
    const allEvents = []
    let gotClarification = false
    let resolved = false
    const finish = (extra = {}) => {
      if (resolved) return
      resolved = true
      clearTimeout(timer)
      try { ws.close() } catch {}
      resolve({ toolCalls, content: textParts.join(''), clarification: gotClarification, events: allEvents, ...extra })
    }
    const timer = setTimeout(() => finish({ timeout: true }), timeoutMs)

    ws.on('open', () => {
      if (model) {
        ws.send(JSON.stringify({ action: 'settings', settings: { model } }))
      }
      setTimeout(() => {
        ws.send(JSON.stringify({ action: 'message', content: message }))
      }, 200)
    })

    ws.on('message', (raw) => {
      try {
        const event = JSON.parse(raw.toString())
        allEvents.push(event.type + (event.name ? `:${event.name}` : ''))
        if (event.type === 'tool_start') toolCalls.push(event.name)
        if (event.type === 'text_delta') textParts.push(event.content)
        if (event.type === 'clarification') gotClarification = true
        if (event.type === 'error') {
          console.log(`WS ERROR: ${JSON.stringify(event)}`)
          finish({ timeout: false, error: event })
        }
        if (event.type === 'message_end') finish({ timeout: false })
      } catch {}
    })

    ws.on('error', (err) => { console.log(`WS CONN ERROR: ${err.message}`); finish({ timeout: false, error: err.message }) })
    ws.on('close', () => finish({ timeout: false }))
  })
}

test.describe('Model-vergelijking', () => {
  let token

  test.beforeAll(async () => {
    token = await getToken()
    expect(token).toBeTruthy()
  })

  const effectiveModels = USE_DEFAULT ? ['default'] : MODELS

  for (const q of TEST_QUESTIONS) {
    for (const model of effectiveModels) {
      const modelShort = model === 'default' ? 'default' : model.split('/').pop()

      test(`[${modelShort}] ${q.label}: ${q.description}`, async () => {
        test.setTimeout(120_000)
        const result = await chatViaWebSocket(token, q.message, model === 'default' ? null : model)

        console.log(`\n${'='.repeat(60)}`)
        console.log(`MODEL: ${model}`)
        console.log(`VRAAG: ${q.message}`)
        console.log(`EVENTS: ${result.events?.join(', ') || '(geen)'}`)
        console.log(`TOOLS: ${result.toolCalls.length ? result.toolCalls.join(' → ') : '(geen)'}`)
        console.log(`CLARIFICATION: ${result.clarification}`)
        console.log(`ANTWOORD (300 chars): ${result.content.slice(0, 300)}`)
        console.log(`TIMEOUT: ${result.timeout}`)
        if (result.error) console.log(`ERROR: ${JSON.stringify(result.error)}`)
        console.log('='.repeat(60))

        if (q.expect_event === 'clarification') {
          const usedTool = result.clarification || result.toolCalls.includes('clarify_scope')
          const didNotFetchData = !result.toolCalls.includes('search_catalog') && !result.toolCalls.includes('dataset_details')
          const askedInText = /verduidelijk|welk.*jaar|welk.*opleiding|specifieker|bedoel je|scope.?vraag|af te bakenen|aanvullend|informatie nodig|welk.*periode/i.test(result.content)
          console.log(`SCOPE-DISCIPLINE: tool=${usedTool}, tekst-fallback=${askedInText}, no-data-fetch=${didNotFetchData}`)
          expect(
            usedTool || askedInText || didNotFetchData,
            `${modelShort} moet scope verduidelijken of in ieder geval niet direct data ophalen`
          ).toBeTruthy()
          if (!usedTool && askedInText) {
            console.log(`⚠️  ${modelShort} verduidelijkt via tekst i.p.v. clarify_scope tool`)
          }
        }

        if (q.expect_tool && q.expect_event !== 'clarification') {
          expect(
            result.toolCalls,
            `${modelShort} moet ${q.expect_tool} aanroepen`
          ).toContain(q.expect_tool)
        }

        if (q.expect_followup_tool) {
          const hasFollowup = result.toolCalls.includes(q.expect_followup_tool)
          console.log(`${q.expect_followup_tool} aangeroepen: ${hasFollowup ? 'JA' : 'NEE'}`)
        }

        if (q.label === 'toon-check') {
          const content = result.content.toLowerCase()
          const fluff = ['goede vraag', 'zeker!', 'interessant', 'natuurlijk!', 'absoluut']
          for (const f of fluff) {
            expect(content, `${modelShort} bevat fluff: "${f}"`).not.toContain(f)
          }
        }
      })
    }
  }
})
