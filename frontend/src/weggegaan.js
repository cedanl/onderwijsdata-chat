import { metDeeltekst } from './turnTrace'

// Wie tijdens een antwoord of rapport wegging, stopte het zelf (#772): dat heet niet "Verbinding verbroken". Het
// antwoord blijft staan zoals het was, gestopt en gemarkeerd; een rapport krijgt een eigen regel met de weg terug.
export const WEGGEGAAN = 'Gestopt omdat je wegging'
export const RAPPORT_WEGGEGAAN = 'Het rapport is gestopt omdat je wegging.'

// `deeltekst`: tekst die nog in de deltabuffer van useChat zat (#510). Een antwoord zonder eigen tekst houdt zijn
// laatste tussentekst (#652), zoals een afgebroken antwoord. Was er nog geen antwoord (het model dacht na), dan staat de
// markering in een leeg antwoord: de vraag erboven blijft niet zonder iets staan.
export function markeerWeggegaan(messages, { rapport = false, id = crypto.randomUUID(), deeltekst = '' } = {}) {
  // Als een mislukt rapport (#515): geen modelbeurt, wel "Opnieuw proberen".
  if (rapport) {
    return [...messages, { id, role: 'assistant', content: RAPPORT_WEGGEGAAN, done: true, isError: true, herstel: 'rapport', weggegaan: true }]
  }
  // Als bij de stopknop: `stopped`, zodat de server die beurt afsluit (#548).
  const gestopt = { done: true, stopped: true, weggegaan: true }
  const i = messages.findLastIndex(m => m.role === 'assistant' && m.done === false)
  if (i < 0) return [...messages, { id, role: 'assistant', content: '', tools: [], ...gestopt }]
  return messages.with(i, metDeeltekst({ ...messages[i], content: messages[i].content + deeltekst, ...gestopt }))
}

// Eindigt het gesprek op zo'n markering, dan opent /chat het bij terugkeer weer (#772). Een grafiek van de gestopte run
// komt als eigen bericht ná het antwoord, en telt niet mee.
export const eindigtWeggegaan = messages => !!messages.findLast(m => !m.figures?.length)?.weggegaan
