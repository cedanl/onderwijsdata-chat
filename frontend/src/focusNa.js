// Waar de focus heen gaat na een actie die het gefocuste element laat verdwijnen (#776): een item
// verwijderen, een gesprek openen. Zonder dit valt de focus op <body> en is een toetsenbord- of
// schermlezergebruiker zijn plek kwijt (WCAG 2.4.3).

// Het item naast `id` in `ids`: het volgende, aan het eind het vorige, anders null.
export function buurVan(ids, id) {
  const i = ids.indexOf(String(id))
  if (i < 0) return null
  return ids[i + 1] ?? ids[i - 1] ?? null
}

// De waarden van `attribuut` van de elementen die nu in het document staan, in documentvolgorde.
export function idsInDocument(kiezer, attribuut) {
  return [...document.querySelectorAll(kiezer)].map(el => el.getAttribute(attribuut))
}

// Een kiezer voor het element met deze id; aanhalingstekens en backslashes in de id breken hem niet.
export function kiezerMetId(kiezer, attribuut, id) {
  return `${kiezer}[${attribuut}="${String(id).replace(/["\\]/g, '\\$&')}"]`
}

// De focus naar het eerste element dat bestaat en hem aanneemt (niet uitgeschakeld, niet inert).
// Lege kiezers tellen niet mee. Geeft terug of het lukte.
export function focusEerste(...kiezers) {
  for (const kiezer of kiezers) {
    if (!kiezer) continue
    const el = document.querySelector(kiezer)
    if (!el) continue
    el.focus()
    if (document.activeElement === el) return true
  }
  return false
}
