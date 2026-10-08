/**
 * Het WebSocket-contract van /api/chat voor de e2e-runners (CH-28, #436). Puur waar het kan,
 * zodat score-unit.mjs het zonder app en zonder LLM toetst.
 *
 * - Het token gaat mee als subprotocol ("bearer", <token>), zoals de frontend doet; de server
 *   leest geen ?token= meer (routes/chat.py).
 * - Het antwoord is de `content` van message_end. Losse text_delta's zijn alleen een tussenstand:
 *   na message_cancel (een ingetrokken versie) tellen ze niet meer mee.
 * - Een einde met `aborted` of `partial` is geen geldig einde.
 */
export const WS_URL = 'ws://localhost:8000/api/chat'

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
