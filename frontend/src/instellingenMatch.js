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
