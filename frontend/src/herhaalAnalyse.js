// "Herhaal deze analyse" (#1240): de CBS-tabellen achter een antwoord opnieuw bij de bron, naast de stand van toen.
// De server (routes/herhaal.py) vergelijkt alleen getallen en bronversie, nooit modeltekst, en roept geen model aan;
// het antwoord zelf verandert niet: de herhaling staat er als tak onder. Een prototype voor CBS; DUO en RIO volgen.
//
// Hier: wanneer de knop er staat, de vaste teksten en de opmaak van de stand (toen en nu). De zin per tabel
// (`samenvatting`) komt van de server, uit tools/brondiff.py. Geen tekst zegt dat het eerdere antwoord niet klopte:
// het rustte op de stand van toen (besluit #1236; herhaalAnalyse.test.js toetst de teksten).

export const HERHAAL_KNOP = 'Herhaal deze analyse'
export const HERHAAL_BEZIG = 'De tabellen worden opnieuw opgehaald bij CBS…'
export const HERHAAL_KOP = 'Herhaald bij de bron'
export const HERHAAL_NOOT = 'Alleen getallen en bronversie zijn naast elkaar gezet, niet de tekst. Het antwoord '
  + 'hierboven blijft staan: het rust op de stand van toen.'
export const REDEN_ZONDER_HASH = 'Herhalen kan alleen via een beveiligde verbinding (https).'
export const STATUS = {
  ongewijzigd: 'Ongewijzigd',
  bijgewerkt: 'Bron bijgewerkt',
  niet_te_vergelijken: 'Alleen de stand van nu',
  mislukt: 'Niet opgehaald',
}

// De stappen die een CBS-tabel laadden of erop selecteerden: zonder zo'n stap is er niets te herhalen.
const CBS_STAPPEN = new Set(['get_cbs_data', 'query_data'])

export function cbsStappen(msg) {
  return (msg?.tools || []).filter(t => t && !t.status && CBS_STAPPEN.has(t.name)
    && typeof t.dataKey === 'string' && t.dataKey.startsWith('cbs:'))
}

// Een afgerond data-antwoord met een CBS-stap; geen rapport (dat is geen bericht in de chat), geen tekst uit code,
// geen fout en geen gestopt antwoord (dat heeft geen bewijsrij op de server).
export function toontHerhaal(msg) {
  return !!msg && msg.role === 'assistant' && msg.done === true && !msg.isError && !msg.stopped
    && !msg.interrupted && msg.vast !== true && Array.isArray(msg.bronnen) && typeof msg.content === 'string'
    && msg.content.length > 0 && cbsStappen(msg).length > 0
}

// De sleutel van het antwoord, zoals de server hem kent (agent/beurtbewijs.py): sha256 (hex) van de tekst.
export function kanHashen() {
  return typeof globalThis.crypto?.subtle?.digest === 'function'
}

export async function antwoordHash(tekst) {
  const bytes = new globalThis.TextEncoder().encode(tekst)
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes)
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('')
}

// 2026-06-15 → 15-06-2026, zoals de bronregels; zonder dag "onbekend".
export function nlDag(iso) {
  const m = typeof iso === 'string' ? /^(\d{4})-(\d{2})-(\d{2})/.exec(iso) : null
  return m ? `${m[3]}-${m[2]}-${m[1]}` : 'onbekend'
}

export function standTekst(stand) {
  if (!stand) return null
  const delen = [`bijgewerkt op ${nlDag(stand.bijgewerkt_op)}`]
  if (stand.hash) delen.push(`inhoudshash ${stand.hash}`)
  return delen.join(', ')
}

// Alle vaste teksten van de knop en de uitkomst, voor de toets op woorden als "fout".
export const VASTE_TEKSTEN = [HERHAAL_KNOP, HERHAAL_BEZIG, HERHAAL_KOP, HERHAAL_NOOT, REDEN_ZONDER_HASH, ...Object.values(STATUS)]
