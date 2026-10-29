import { STORAGE_TE_VERWIJDEREN } from './constants'
import { deleteConversationApi } from './api'
import { volgOpslag } from './gesprekOpslag'

// De gesprekken waarvan de verwijdering gepland is en die de server nog niet bevestigde (#801). Sluit de tab binnen de
// bedenktijd (#493), dan gaat de DELETE mee met het sluiten; mislukte die, dan was er geen pagina meer om het te
// zeggen en stond het gesprek bij het volgende bezoek weer in de lijst. Nu blijft het id hier tot een DELETE lukt (een
// 404 telt mee, api.js), de verwijdering ongedaan wordt gemaakt of er weer een vraag in het gesprek komt (#535), en
// gaat het bij het volgende laden van de chat opnieuw. Alleen ids, geen titel of inhoud. De wachtrij hoort bij het
// account: ze staat in SESSION_DATA_KEYS, en uitloggen stuurt haar eerst nog met het eigen token.

export function inWachtrij() {
  try {
    const ids = JSON.parse(localStorage.getItem(STORAGE_TE_VERWIJDEREN) || '[]')
    return Array.isArray(ids) ? ids.map(String) : []
  } catch {
    return []
  }
}

function bewaar(ids) {
  try {
    if (ids.length) localStorage.setItem(STORAGE_TE_VERWIJDEREN, JSON.stringify(ids))
    else localStorage.removeItem(STORAGE_TE_VERWIJDEREN)
  } catch {
    // Vol of geblokkeerd: de verwijdering gaat dan zonder herkansing bij het volgende bezoek.
  }
}

export function zetInWachtrij(id) {
  const ids = inWachtrij()
  if (!ids.includes(String(id))) bewaar([...ids, String(id)])
}

// Elke keer opnieuw gelezen, zonder kopie in het geheugen: een DELETE die pas na het uitloggen klaar is, schrijft de
// gewiste wachtrij zo niet terug.
export function haalUitWachtrij(id) {
  const ids = inWachtrij()
  if (ids.includes(String(id))) bewaar(ids.filter(x => x !== String(id)))
}

// De lijst zonder de gesprekken in `ids` (standaard: wat nu in de wachtrij staat).
export function zonderTeVerwijderen(lijst, ids = inWachtrij()) {
  return lijst.filter(c => !ids.includes(String(c.id)))
}

// De DELETE's die nu lopen. Een id dat al onderweg is (uitloggen binnen de bedenktijd, de dubbele eerste render van
// StrictMode) krijgt dezelfde belofte en geen tweede verzoek.
const onderweg = new Map()

// Een gesprek op de server verwijderen. De DELETE mag de pagina overleven (keepalive, tab sluiten, #493) en loopt mee
// in volgOpslag, zodat uitloggen het token pas intrekt als ze klaar is (#778). Lukt ze, dan gaat het id uit de
// wachtrij; mislukt ze, dan blijft het staan en wijst de belofte af.
export function verwijderGesprek(id) {
  const sleutel = String(id)
  if (onderweg.has(sleutel)) return onderweg.get(sleutel)
  const verzoek = volgOpslag(deleteConversationApi(sleutel, { keepalive: true })).then(() => haalUitWachtrij(sleutel))
  onderweg.set(sleutel, verzoek)
  const klaar = () => { onderweg.delete(sleutel) }
  verzoek.then(klaar, klaar)
  return verzoek
}

// Elk gesprek in de wachtrij nu verwijderen: bij het laden van de chat, en bij het uitloggen zolang het token er nog
// is. `opMislukt(id)` hoort welk gesprek weer niet lukte. Geeft de ids terug die nu gaan.
export function verstuurWachtrij(opMislukt = () => {}) {
  const ids = inWachtrij()
  for (const id of ids) verwijderGesprek(id).catch(() => opMislukt(id))
  return ids
}
