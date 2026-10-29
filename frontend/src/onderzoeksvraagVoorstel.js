// The research question a report starts from (#751), filled in for the user to confirm or change (#732). The chat
// writes a line "**Onderzoeksvraag:** …" with every answer with data (prompts/system.md), with the scope the
// conversation gave it so far: the one in the latest answer wins. Without such a line, the first question of the
// conversation, which is also what the server takes when the field stays empty.

// The label at the start of a line, in or after a quote or list item, with the bold before or after the colon.
const REGEL = /^[\s>-]*(?:\*\*|__)?\s*onderzoeksvraag\s*(?:\*\*|__)?\s*:\s*(?:\*\*|__)?(.*)$/gim
// Emphasis around the question itself ("*Hoe …?*"); the text stays one line.
const NADRUK = /^[*_\s]+|[*_\s]+$/g

const schoon = tekst => tekst.replace(/\*\*|__/g, '').replace(NADRUK, '').replace(/\s+/g, ' ').trim()

// Stopped, cut off by a dropped connection, or an error: the line in it may be half a sentence.
const afgebroken = m => !!(m.interrupted || m.stopped || m.afgebroken || m.isError)

function regelUit(content) {
  const vragen = [...content.matchAll(REGEL)].map(([, tekst]) => schoon(tekst)).filter(Boolean)
  return vragen.at(-1) ?? null
}

export function onderzoeksvraagVoorstel(messages) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i]
    if (m.role !== 'assistant' || typeof m.content !== 'string' || afgebroken(m)) continue
    const vraag = regelUit(m.content)
    if (vraag) return vraag
  }
  const eerste = messages.find(m => m.role === 'user' && !m.isError && typeof m.content === 'string' && m.content.trim())
  return eerste ? eerste.content.replace(/\s+/g, ' ').trim() : ''
}
