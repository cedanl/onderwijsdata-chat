/**
 * Het WebSocket-contract van /api/chat voor de e2e-runners (CH-28, #436). Puur waar het kan,
 * zodat score-unit.mjs het zonder app en zonder LLM toetst.
 *
 * - Het token gaat mee als subprotocol ("bearer", <token>), zoals de frontend doet; de server
 *   leest geen ?token= meer (routes/chat.py).
 * - Het antwoord is de `content` van message_end. Losse text_delta's zijn alleen een tussenstand:
 *   na message_cancel (een ingetrokken versie) tellen ze niet meer mee.
 * - Een einde met `aborted` of `partial` is geen geldig einde.
 * - De omgeving komt uit EVAL_BASE_URL (standaard de lokale app) en de inloggegevens uit
 *   EVAL_USERNAME/EVAL_PASSWORD (standaard admin/admin): zo draait dezelfde runner tegen de
 *   testomgeving als synthetische controle, los van de modelantwoordketen (#169).
 */
export const BASE_URL = (process.env.EVAL_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')

/** De WebSocket-URL van /api/chat bij een http(s)-basis: https wordt wss. */
export function wsUrl(base = BASE_URL) {
  return base.replace(/^http/, 'ws').replace(/\/+$/, '') + '/api/chat'
}

export const WS_URL = wsUrl()

/** Gebruikersnaam en wachtwoord voor /api/auth/login, uit de omgeving of de lokale standaard. */
export function inloggegevens(env = process.env) {
  return { username: env.EVAL_USERNAME || 'admin', password: env.EVAL_PASSWORD || 'admin' }
}

// De limieten van de app tegen één account (#444, #504): 30 verzoeken die het model kosten per 10 minuten, en 5
// inlogpogingen per minuut. Een eval-run stelt er meer, en na een mislukte test logt een nieuwe worker opnieuw in.
// Zonder te wachten faalde de run van 04-11 vanaf de tiende minuut op elke vraag (#909).
const MAX_WACHTRONDES = 5
const LIMIET = /Te veel verzoeken in korte tijd\. Probeer het over (\d+) seconden opnieuw\./

/** De wachttijd in seconden uit de melding van de berichtlimiet; null bij een andere of geen melding. */
export function limietWacht(melding) {
  const m = LIMIET.exec(melding || '')
  return m ? Number(m[1]) : null
}

export const slaap = (ms) => new Promise(klaar => setTimeout(klaar, ms))

/** Het token van /api/auth/login met de inloggegevens uit de omgeving; bij 429 eerst de Retry-After afwachten. */
export async function haalToken(base = BASE_URL) {
  for (let ronde = 0; ; ronde++) {
    const resp = await fetch(`${base}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(inloggegevens()),
    })
    if (resp.status !== 429 || ronde >= MAX_WACHTRONDES) return (await resp.json()).token
    const wacht = Number(resp.headers.get('retry-after')) || 60
    console.log(`  INLOGLIMIET: ${wacht} s wachten`)
    await slaap((wacht + 1) * 1000)
  }
}

/**
 * Doe `verzoek` opnieuw zolang de berichtlimiet het weigert, na de wachttijd uit de melding. Alleen als er nog niets
 * gebeurde: de server weigert vóór de run, dus het gesprek kent het geweigerde verzoek niet.
 */
export async function binnenLimiet(verzoek, wachtFn = slaap) {
  for (let ronde = 0; ; ronde++) {
    const uit = await verzoek()
    const wacht = limietWacht(uit.error)
    if (wacht === null || ronde >= MAX_WACHTRONDES || uit.toolCalls?.length || uit.content) return uit
    console.log(`  BERICHTLIMIET: ${wacht} s wachten`)
    await wachtFn((wacht + 1) * 1000)
  }
}

/** De subprotocollen voor `new WebSocket(WS_URL, protocollen(token))`, zoals de frontend ze stuurt. */
export function protocollen(token) {
  return ['bearer', token]
}

export function nieuwAntwoord() {
  return { toolCalls: [], bronnen: [], toolResults: [], delen: [], content: '', ingetrokken: 0, einde: null, error: null }
}

// De argumenten van tool_start die zeggen welke bron en dataset een tool aanspreekt (#909).
const BRONARGUMENTEN = ['dataset_id', 'resource', 'maat']

/** Welke bron een tool_start aanspreekt, als { tool, dataset_id?, resource?, maat? }; null bij een tool zonder bron. */
export function bronVan(event) {
  const input = event.input && typeof event.input === 'object' ? event.input : {}
  const gekozen = BRONARGUMENTEN.filter(k => input[k] !== undefined && input[k] !== null && input[k] !== '')
  return gekozen.length ? { tool: event.name, ...Object.fromEntries(gekozen.map(k => [k, input[k]])) } : null
}

/** Verwerk één server-event in het antwoord (muteert en geeft het terug). */
export function verwerk(a, event) {
  switch (event.type) {
    case 'tool_start': {
      a.toolCalls.push(event.name)
      const bron = bronVan(event)
      if (bron) a.bronnen.push(bron)
      break
    }
    case 'tool_end':
      a.toolResults.push({ name: event.name, output: (event.output || '').slice(0, 500) })
      break
    case 'text_delta':
      a.delen.push(event.content || '')
      break
    case 'message_cancel':
      // De versie tot nu toe is ingetrokken: wat volgt, vervangt haar.
      a.delen = []
      a.ingetrokken += 1
      break
    case 'message_end':
      a.content = typeof event.content === 'string' ? event.content : a.delen.join('')
      a.einde = event.aborted ? 'afgebroken' : event.partial ? 'gedeeltelijk' : 'geldig'
      break
    case 'error':
      a.error = event.message || 'onbekende fout'
      break
  }
  return a
}

/** De harde eisen aan elk resultaat, vóór enige score: één zachte totaalscore verbergt ze. */
export function poorten(r) {
  return {
    geldig_einde: r.einde === 'geldig',
    tekst: (r.content || '').trim() !== '',
    geen_fout: !r.error,
    geen_timeout: !r.timeout,
  }
}
