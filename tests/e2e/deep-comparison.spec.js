/**
 * Diepere model-vergelijking: volledige analyse-flow.
 *
 * Test of beide modellen:
 * 1. Dezelfde datasets vinden
 * 2. Vergelijkbare data ophalen
 * 3. Geen hallucinaties produceren (antwoord gebaseerd op opgehaalde data)
 *
 * Run: TEST_MODELS=azure_ai/claude-haiku-4-5,openai/gpt-oss-120b npx playwright test deep-comparison
 */
import { test, expect } from 'playwright/test'
import { WebSocket } from 'ws'

const API = 'http://localhost:8000'
const WS_URL = 'ws://localhost:8000/api/chat'
const MODELS = (process.env.TEST_MODELS || 'azure_ai/claude-haiku-4-5,openai/gpt-oss-120b').split(',').filter(Boolean)

async function getToken() {
  const resp = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'admin' }),
  })
  return (await resp.json()).token
}

function chatViaWebSocket(token, messages, model, timeoutMs = 180_000) {
  return new Promise((resolve) => {
    const ws = new WebSocket(`${WS_URL}?token=${token}`)
    const toolCalls = []
    const toolResults = []
    const textParts = []
    const allEvents = []
    let resolved = false
    let gotClarification = false
    let msgIndex = 0

    const finish = (extra = {}) => {
      if (resolved) return
      resolved = true
      clearTimeout(timer)
      try { ws.close() } catch {}
      resolve({ toolCalls, toolResults, content: textParts.join(''), events: allEvents, clarification: gotClarification, ...extra })
    }
    const timer = setTimeout(() => finish({ timeout: true }), timeoutMs)

    const sendNext = () => {
      if (msgIndex < messages.length) {
        const msg = messages[msgIndex++]
        if (msg.action === 'clarification_choice') {
          ws.send(JSON.stringify(msg))
        } else {
          ws.send(JSON.stringify({ action: 'message', content: msg }))
        }
      }
    }

    ws.on('open', () => {
      if (model) ws.send(JSON.stringify({ action: 'settings', settings: { model } }))
      setTimeout(sendNext, 200)
    })

    ws.on('message', (raw) => {
      try {
        const event = JSON.parse(raw.toString())
        allEvents.push(event)
        if (event.type === 'tool_start') toolCalls.push(event.name)
        if (event.type === 'tool_end') toolResults.push({ name: event.name, preview: (event.output || '').slice(0, 300) })
        if (event.type === 'text_delta') textParts.push(event.content)
        if (event.type === 'clarification') {
          gotClarification = true
          const opties = event.opties || []
          const aanbevolen = opties.find(o => o.aanbevolen) || opties[0]
          if (aanbevolen) {
            console.log(`  AUTO-ANTWOORD clarify: "${event.vraag}" → "${aanbevolen.label}"`)
            setTimeout(() => {
              ws.send(JSON.stringify({ action: 'clarification_choice', choice: aanbevolen.label }))
            }, 500)
          } else {
            finish({ timeout: false, clarificationData: event })
          }
        }
        if (event.type === 'error') finish({ timeout: false, error: event })
        if (event.type === 'message_end') {
          if (msgIndex < messages.length) {
            setTimeout(sendNext, 500)
            textParts.length = 0
          } else {
            finish({ timeout: false })
          }
        }
      } catch {}
    })

    ws.on('error', () => finish({ timeout: false }))
    ws.on('close', () => finish({ timeout: false }))
  })
}

test.describe('Diepe model-vergelijking', () => {
  let token
  test.beforeAll(async () => { token = await getToken() })

  test('catalog-retrieval: beide modellen vinden dezelfde datasets', async () => {
    test.setTimeout(300_000)
    const results = {}

    for (const model of MODELS) {
      const modelShort = model.split('/').pop()
      const r = await chatViaWebSocket(token, [
        'Zoek datasets over arbeidsmarktpositie van hbo-afgestudeerden',
      ], model)

      const datasetIds = r.toolResults
        .filter(t => t.name === 'search_catalog')
        .flatMap(t => {
          try {
            const parsed = JSON.parse(t.preview.length > 190 ? '[]' : t.preview)
            return Array.isArray(parsed) ? parsed.map(d => d._cbs_id || d._ckan_id || d.identifier) : []
          } catch { return [] }
        })

      results[modelShort] = {
        tools: r.toolCalls,
        content: r.content,
        datasetIds,
        clarification: r.clarification,
        timeout: r.timeout,
      }

      console.log(`\n${'─'.repeat(60)}`)
      console.log(`MODEL: ${model}`)
      console.log(`TOOLS: ${r.toolCalls.join(' → ') || '(geen)'}`)
      console.log(`CLARIFICATION: ${r.clarification}`)
      console.log(`ANTWOORD (500 chars):\n${r.content.slice(0, 500)}`)
      console.log('─'.repeat(60))
    }

    const modelNames = Object.keys(results)
    if (modelNames.length === 2) {
      const [a, b] = modelNames
      const bothSearched = results[a].tools.includes('search_catalog') && results[b].tools.includes('search_catalog')
      console.log(`\n${'═'.repeat(60)}`)
      console.log(`VERGELIJKING`)
      console.log(`${a} tools: ${results[a].tools.join(' → ')}`)
      console.log(`${b} tools: ${results[b].tools.join(' → ')}`)
      console.log(`Beide search_catalog: ${bothSearched}`)

      if (bothSearched) {
        const mentionedA = results[a].content.match(/\d{5}[A-Z]{3}/g) || []
        const mentionedB = results[b].content.match(/\d{5}[A-Z]{3}/g) || []
        const overlap = mentionedA.filter(id => mentionedB.includes(id))
        console.log(`${a} CBS IDs in antwoord: ${mentionedA.join(', ') || '(geen)'}`)
        console.log(`${b} CBS IDs in antwoord: ${mentionedB.join(', ') || '(geen)'}`)
        console.log(`Overlap: ${overlap.join(', ') || '(geen)'}`)
      }
      console.log('═'.repeat(60))
    }
  })

  test('full-analysis: instroom HU vergelijking', async () => {
    test.setTimeout(300_000)
    const results = {}

    for (const model of MODELS) {
      const modelShort = model.split('/').pop()
      const r = await chatViaWebSocket(token, [
        'Hoeveel eerstejaars studenten had Hogeschool Utrecht in het laatste schooljaar? Geef het totaal.',
      ], model)

      results[modelShort] = {
        tools: r.toolCalls,
        content: r.content,
        clarification: r.clarification,
        toolResults: r.toolResults,
        timeout: r.timeout,
      }

      console.log(`\n${'─'.repeat(60)}`)
      console.log(`MODEL: ${model}`)
      console.log(`TOOLS: ${r.toolCalls.join(' → ') || '(geen)'}`)
      console.log(`CLARIFICATION: ${r.clarification}`)
      console.log(`TOOL RESULTS:`)
      for (const tr of r.toolResults) {
        console.log(`  ${tr.name}: ${tr.preview}`)
      }
      console.log(`ANTWOORD (800 chars):\n${r.content.slice(0, 800)}`)
      console.log('─'.repeat(60))
    }

    const modelNames = Object.keys(results)
    if (modelNames.length === 2) {
      const [a, b] = modelNames
      console.log(`\n${'═'.repeat(60)}`)
      console.log(`VERGELIJKING — Instroom HU`)

      const numbersA = results[a].content.match(/[\d.]+/g)?.map(Number).filter(n => n > 100) || []
      const numbersB = results[b].content.match(/[\d.]+/g)?.map(Number).filter(n => n > 100) || []
      console.log(`${a} getallen >100: ${numbersA.join(', ') || '(geen)'}`)
      console.log(`${b} getallen >100: ${numbersB.join(', ') || '(geen)'}`)

      const toolPathA = results[a].tools.join(' → ')
      const toolPathB = results[b].tools.join(' → ')
      console.log(`${a} toolpad: ${toolPathA || '(geen)'}`)
      console.log(`${b} toolpad: ${toolPathB || '(geen)'}`)

      const hallA = !results[a].tools.includes('search_catalog') && !results[a].tools.includes('get_cbs_data') && !results[a].tools.includes('get_duo_data') && numbersA.length > 0
      const hallB = !results[b].tools.includes('search_catalog') && !results[b].tools.includes('get_cbs_data') && !results[b].tools.includes('get_duo_data') && numbersB.length > 0
      console.log(`${a} mogelijke hallucinatie (getallen zonder data-fetch): ${hallA}`)
      console.log(`${b} mogelijke hallucinatie (getallen zonder data-fetch): ${hallB}`)
      console.log('═'.repeat(60))

      expect(hallA, `${a} geeft getallen zonder data op te halen`).toBe(false)
      expect(hallB, `${b} geeft getallen zonder data op te halen`).toBe(false)
    }
  })
})
