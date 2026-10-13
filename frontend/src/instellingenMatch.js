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

function afstand(a, b) {
  let vorige = Array.from({ length: b.length + 1 }, (_, j) => j)
  for (let i = 1; i <= a.length; i++) {
    const huidige = [i]
    for (let j = 1; j <= b.length; j++) {
      huidige[j] = Math.min(vorige[j] + 1, huidige[j - 1] + 1, vorige[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1))
    }
    vorige = huidige
  }
  return vorige[b.length]
}

// "Bedoel je …?" (#496 F04): de instellingen waarvan naam of afkorting op een typefout na lijkt op de
// zoekterm, de dichtstbijzijnde eerst, hoogstens `max`. Een enkel woord wordt ook tegen elk woord van
// de naam gehouden ("Hogescool" → Hogeschool Utrecht). De drempel schaalt mee met de lengte, zodat
// een korte afkorting niet bij alles past.
export function suggereerInstellingen(zoekterm, instellingen, max = 3) {
  const q = normalize(zoekterm)
  if (q.length < 3) return []
  const drempel = Math.max(1, Math.floor(q.length / 4))
  const enkelWoord = !q.includes(' ')
  const gevonden = []
  for (const inst of instellingen || []) {
    const kandidaten = [inst.naam, ...(inst.aliassen || [])].map(normalize)
    const vormen = kandidaten.flatMap(k => (enkelWoord ? [k, ...k.split(/\s+/)] : [k]))
    const beste = Math.min(...vormen.map(v => afstand(q, v)))
    if (beste <= drempel) gevonden.push({ inst, beste })
  }
  return gevonden
    .sort((a, b) => a.beste - b.beste || a.inst.naam.localeCompare(b.inst.naam, 'nl'))
    .slice(0, max)
    .map(g => g.inst)
}
