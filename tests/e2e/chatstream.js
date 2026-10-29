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

/** Het token van /api/auth/login met de inloggegevens uit de omgeving. */
export async function haalToken(base = BASE_URL) {
  const resp = await fetch(`${base}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(inloggegevens()),
  })
  return (await resp.json()).token
}

/** De subprotocollen voor `new WebSocket(WS_URL, protocollen(token))`, zoals de frontend ze stuurt. */
export function protocollen(token) {
  return ['bearer', token]
}

export function nieuwAntwoord() {
  return { toolCalls: [], toolResults: [], delen: [], content: '', ingetrokken: 0, einde: null, error: null }
}

/** Verwerk één server-event in het antwoord (muteert en geeft het terug). */
export function verwerk(a, event) {
  switch (event.type) {
    case 'tool_start':
      a.toolCalls.push(event.name)
      break
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
