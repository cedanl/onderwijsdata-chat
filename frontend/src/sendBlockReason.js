// Waarom een vraag nu niet weg kan, als één korte reden (#585; eerder #241). Eerst wat aan de chat ligt, dan wat
// aan het concept: wie op een antwoord wacht, heeft niets aan "Typ eerst een vraag". Wat vanzelf overgaat,
// begint met "Even wachten:".
const REDENEN = {
  busy: 'Even wachten: het vorige antwoord is nog bezig',
  reporting: 'Even wachten: er wordt een rapport gemaakt',
  resetting: 'Even wachten: het nieuwe gesprek wordt gestart',
  offline: 'Geen verbinding',
  full: 'Chat is vol: begin een nieuw gesprek',
  empty: 'Typ eerst een vraag',
  over: 'Bericht te lang',
  refused: 'Even wachten: probeer het zo opnieuw',
}

const reden = key => ({ key, text: REDENEN[key] })

// Wat aan de chat ligt, los van het concept; null als de chat een vraag aanneemt.
export function chatBlockReason({ connected, busy, resetting, reporting, atContextLimit }) {
  if (busy) return reden('busy')
  if (reporting) return reden('reporting')
  if (resetting) return reden('resetting')
  if (!connected) return reden('offline')
  if (atContextLimit) return reden('full')
  return null
}

// { key, text } of null als de vraag weg kan.
export function sendBlockReason({ text = '', over = false, ...chat }) {
  const aanDeChat = chatBlockReason(chat)
  if (aanDeChat) return aanDeChat
  if (!text.trim()) return reden('empty')
  return over ? reden('over') : null
}

// send() weigerde toch: de toestand liep voor op de render, of de vraag kwam van elders ("Opnieuw").
export function refusalReason(chat) {
  return chatBlockReason(chat) ?? reden('refused')
}
