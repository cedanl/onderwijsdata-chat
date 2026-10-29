/**
 * Een gesprek over één WebSocket voor de e2e-runners: de sessie van de server hoort bij de verbinding, dus een
 * vervolgvraag en een rapport erna moeten over dezelfde socket (#752). `vraag` is één beurt zoals de chat hem
 * geeft; `rapport` vraagt het rapport op zoals de app dat doet (#751), met de onderzoeksvraag erbij.
 */
import { WebSocket } from 'ws'
import { WS_URL, nieuwAntwoord, protocollen, verwerk } from './chatstream.js'

// Na een message_end kan nog een verduidelijkingsvraag volgen (agent/run.py sluit eerst de
// lopende tekst af); pas als die uitblijft, is het antwoord af.
export const NA_EINDE_MS = 1_000
export const VRAAG_TIMEOUT_MS = 300_000
// Zoals REPORT_TIMEOUT_MS in de app (useChat.js): daarna geldt een rapport als mislukt.
export const RAPPORT_TIMEOUT_MS = 600_000

/** Open een gesprek met `model`; het belooft het gesprek zodra de instellingen verstuurd zijn. */
export function verbind(token, model, url = WS_URL) {
  return new Promise((resolve) => {
    const ws = new WebSocket(url, protocollen(token))
    let luisteraar = null
    let verbroken = null

    ws.on('message', (raw) => {
      let event
      try { event = JSON.parse(raw.toString()) } catch { return }
      luisteraar?.(event)
    })
    // Een weigering bij de handshake (4001) of een verbroken verbinding is een fout, geen leeg succes.
    ws.on('error', (err) => { verbroken ??= `verbinding: ${err.message}`; luisteraar?.({ type: 'verbroken' }) })
    ws.on('close', (code) => { verbroken ??= `verbinding gesloten (${code})`; luisteraar?.({ type: 'verbroken' }) })

    /** Wacht tot `stap` met een uitkomst afrondt; daarna luistert niemand meer. */
    function wacht(timeoutMs, stap) {
      return new Promise((klaar) => {
        let af = false
        const rond = (uitkomst) => {
          if (af) return
          af = true
          clearTimeout(timer)
          luisteraar = null
          klaar(uitkomst)
        }
        const timer = setTimeout(() => rond({ timeout: true }), timeoutMs)
        luisteraar = (event) => stap(event, rond)
        if (verbroken) luisteraar({ type: 'verbroken' })
      })
    }

    const gesprek = {
      /** Eén beurt: het antwoord zoals chatstream.verwerk het opbouwt; een verduidelijking krijgt de aanbevolen optie. */
      async vraag(tekst, timeoutMs = VRAAG_TIMEOUT_MS) {
        const antwoord = nieuwAntwoord()
        let naEinde = null
        ws.send(JSON.stringify({ action: 'message', content: tekst }))
        const extra = await wacht(timeoutMs, (event, rond) => {
          if (event.type === 'verbroken') return rond(antwoord.einde ? {} : { error: antwoord.error || verbroken })
          verwerk(antwoord, event)
          if (event.type === 'clarification') {
            clearTimeout(naEinde)
            antwoord.einde = null
            const opties = event.opties || []
            const keuze = opties.find(o => o.aanbevolen) || opties[0]
            if (!keuze) return rond({})
            console.log(`  CLARIFY: "${event.vraag}" → "${keuze.label}"`)
            setTimeout(() => ws.send(JSON.stringify({ action: 'clarification_choice', choice: keuze.label })), 500)
          }
          if (event.type === 'error') {
            console.log(`  ERROR: ${event.message}`)
            rond({})
          }
          if (event.type === 'message_end') {
            clearTimeout(naEinde)
            naEinde = setTimeout(() => rond({}), NA_EINDE_MS)
          }
        })
        clearTimeout(naEinde)
        return { ...antwoord, ...extra }
      },

      /** Het rapport: { spec } bij report_ready, anders { error } of { timeout }. */
      rapport({ onderzoeksvraag, auteur = 'eval' } = {}, timeoutMs = RAPPORT_TIMEOUT_MS) {
        const vraag = (onderzoeksvraag || '').trim()
        ws.send(JSON.stringify({ action: 'generate_report', author: auteur, ...(vraag && { onderzoeksvraag: vraag }) }))
        return wacht(timeoutMs, (event, rond) => {
          if (event.type === 'verbroken') return rond({ error: verbroken })
          if (event.type === 'report_ready') return rond({ spec: event.spec })
          if (event.type === 'report_error') return rond({ error: event.message || 'report_error zonder melding' })
          if (event.type === 'report_cancelled') return rond({ error: 'rapport geannuleerd' })
          // Een weigering vóór de run (busy, verzoeklimiet, te lange vraag) komt als busy of error.
          if (event.type === 'busy' || event.type === 'error') return rond({ error: event.message || event.type })
        })
      },

      sluit() {
        try { ws.close() } catch {}
      },
    }

    ws.on('open', () => {
      ws.send(JSON.stringify({ action: 'settings', settings: { model } }))
      setTimeout(() => resolve(gesprek), 200)
    })
    // Gaat de verbinding meteen mis, dan meldt de eerste stap dat; het gesprek bestaat dan toch.
    ws.once('close', () => resolve(gesprek))
  })
}

/** Eén losse vraag in een eigen gesprek, zoals real-questions.spec.js die stelt. */
export async function losseVraag(token, tekst, model, timeoutMs = VRAAG_TIMEOUT_MS) {
  const gesprek = await verbind(token, model)
  try {
    return await gesprek.vraag(tekst, timeoutMs)
  } finally {
    gesprek.sluit()
  }
}
