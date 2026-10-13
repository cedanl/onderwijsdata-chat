// Match SRAM-derived identity values (org / institution) against the known
// instellingen list the app provides (the same list InstellingPicker shows).
// Returns the canonical instelling name when there is a match, otherwise null.

function normalize(name) {
  return (name || '').trim().toLowerCase()
}

// For an email-address candidate, also match on its domain part.
function candidateKeys(candidate) {
  const normalized = normalize(candidate)
  const keys = [normalized]
  const at = normalized.indexOf('@')
  if (at >= 0) keys.push(normalized.slice(at + 1))
  return keys
}

export function buildInstellingenLookup(instellingen) {
  const lookup = new Map()
  for (const inst of instellingen || []) {
    if (!inst || !inst.naam) continue
    lookup.set(normalize(inst.naam), inst.naam)
    for (const alias of inst.aliassen || []) {
      lookup.set(normalize(alias), inst.naam)
    }
    for (const domein of inst.domeinen || []) {
      lookup.set(normalize(domein), inst.naam)
    }
  }
  return lookup
}

export function matchKnownInstelling(candidates, instellingen) {
  const lookup = buildInstellingenLookup(instellingen)
  if (lookup.size === 0) return null
  for (const candidate of candidates || []) {
    for (const key of candidateKeys(candidate)) {
      const hit = lookup.get(key)
      if (hit) return hit
    }
  }
  return null
}
// The sector (mbo, hbo, wo) of the profile institution, by exact name or alias; free text that
// is not in the list gets null rather than a guess (#447).
export function instellingType(naam, instellingen) {
  const key = normalize(naam)
  if (!key) return null
  const inst = (instellingen || []).find(i => [i.naam, ...(i.aliassen || [])].some(n => normalize(n) === key))
  return inst?.type || null
}

// Levenshtein: de laatste rij geeft de afstand van `a` tot elk begin van `b` (index = lengte van dat begin).
function afstandRij(a, b) {
  let vorige = Array.from({ length: b.length + 1 }, (_, j) => j)
  for (let i = 1; i <= a.length; i++) {
    const huidige = [i]
    for (let j = 1; j <= b.length; j++) {
      huidige[j] = Math.min(vorige[j] + 1, huidige[j - 1] + 1, vorige[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1))
    }
    vorige = huidige
  }
  return vorige
}

const afstand = (a, b) => afstandRij(a, b)[b.length]

// Vulwoorden mogen in een zoekterm staan zonder dat de naam ze heeft ("hogeschool van utrecht").
const VULWOORDEN = new Set(['van', 'de', 'der', 'den', 'het', 'voor', 'en', 'of', 'the', 'in'])

const woorden = tekst => tekst.split(/[^\p{L}\p{N}]+/u).filter(Boolean)

// Hoe dicht een zoekwoord bij een woord van de naam komt, of null als geen woord binnen de drempel valt.
// Het begin van een naamwoord telt ook, zodat een half getypt woord past ("amst", "vam" → "am…").
// Woorden korter dan 3 tekens moeten exact passen.
function woordAfstand(woord, naamwoorden) {
  const drempel = woord.length < 3 ? 0 : Math.max(1, Math.floor(woord.length / 4))
  const beste = Math.min(...naamwoorden.map(n => Math.min(...afstandRij(woord, n))))
  return beste <= drempel ? beste : null
}

// Een zoekterm van meer woorden (#533): elk woord moet een woord van de naam raken, in welke volgorde
// ook; een vulwoord mag missen. De score is de opgetelde afstand, null als de naam niet past.
function woordenScore(zoekwoorden, naam) {
  const naamwoorden = woorden(naam)
  let som = 0
  let geraakt = 0
  for (const woord of zoekwoorden) {
    const a = woordAfstand(woord, naamwoorden)
    if (a === null && !VULWOORDEN.has(woord)) return null
    if (a === null) continue
    som += a
    if (!VULWOORDEN.has(woord)) geraakt++
  }
  return geraakt > 0 ? som : null
}

// Hoe goed een instelling bij de zoekterm past, of null. `beste` is de kleinste afstand van de vormen hieronder;
// `heel` (afstand tot de hele naam) breekt bij meer woorden een gelijkspel, zodat "universiteit utrect"
// Universiteit Utrecht vóór Theologische Universiteit Utrecht zet. Bij één woord blijft het 0: volgorde als voorheen.
function score(q, inst) {
  const drempel = Math.max(1, Math.floor(q.length / 4))
  const enkelWoord = !q.includes(' ')
  const kandidaten = [inst.naam, ...(inst.aliassen || [])].map(normalize)
  const vormen = kandidaten.flatMap(k => (enkelWoord ? [k, ...k.split(/\s+/)] : [k]))
  const heel = vormen.map(v => afstand(q, v))
  const scores = heel.filter(s => s <= drempel)
  if (!enkelWoord) scores.push(...kandidaten.map(k => woordenScore(woorden(q), k)).filter(s => s !== null))
  if (!scores.length) return null
  return { beste: Math.min(...scores), heel: enkelWoord ? 0 : Math.min(...heel) }
}

// "Bedoel je …?" (#496 F04): de instellingen waarvan naam of afkorting op een typefout na lijkt op de
// zoekterm, de dichtstbijzijnde eerst, hoogstens `max`. Een enkel woord wordt ook tegen elk woord van
// de naam gehouden ("Hogescool" → Hogeschool Utrecht), meer woorden ook per woord (woordenScore, #533).
// De drempel schaalt mee met de lengte, zodat een korte afkorting niet bij alles past.
export function suggereerInstellingen(zoekterm, instellingen, max = 3) {
  const q = normalize(zoekterm)
  if (q.length < 3) return []
  return (instellingen || [])
    .map(inst => ({ inst, ...score(q, inst) }))
    .filter(g => g.beste !== undefined)
    .sort((a, b) => a.beste - b.beste || a.heel - b.heel || a.inst.naam.localeCompare(b.inst.naam, 'nl'))
    .slice(0, max)
    .map(g => g.inst)
}
