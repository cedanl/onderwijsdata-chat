/**
 * Antwoordcorrectheid voor de eval-score (#463). Puur, zodat score-unit.mjs het zonder app en
 * zonder LLM toetst.
 *
 * - Alleen het eindantwoord bewijst een referentiewaarde (waardeInAntwoord). De tooluitvoer
 *   bewijst los daarvan dat de bron de waarde gaf (waardeInBron), nooit dat het antwoord klopt.
 * - Getallen matchen op getalgrenzen: 129.941 en 29.9411 zijn geen 29941; 29.941, 29 941 en
 *   29941 wel.
 * - Een waarde is gebonden aan haar context. Het jaar staat in dezelfde zin, regel of tabelrij;
 *   binnen een zin hoort een getal bij het jaar in zijn eigen deelzin (tussen komma's), anders
 *   bij het dichtstbijzijnde jaar. Noemt de case een instelling of maat (data_points.entity /
 *   maat), dan staat die in dezelfde zin of in de kop: de regel boven een lijst of tabel, of een
 *   regel op ':' direct boven de zin.
 */

// Eén getal: met duizendtalscheiding (punt, spatie, NBSP, U+202F) en decimale komma, of kaal.
// Nooit midden in een ander getal: 129.941 levert 129941, niet 29941.
const GETAL = /(?<![\d.,])(?:\d{1,3}([.   ])\d{3}(?:\1\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)(?!\d)/g
const GEGROEPEERD = /^\d{1,3}([.   ])\d{3}(?:\1\d{3})*(?:,\d+)?$/
// In tooluitvoer (JSON, CSV) staan getallen kaal of Engels genoteerd.
const BRONGETAL = /(?<![\d.,])\d+(?:[.,]\d+)*(?!\d)/g
const JAAR = /^(?:19|20)\d{2}$/

const LIJSTITEM = /^\s*(?:[-*•+]|\d+[.)])\s+/
const TABELRIJ = /^\s*\|/
const TABELSCHEIDING = /^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$/
const ZINSGRENS = /(?<=[.!?])\s+(?=\p{Lu})|;/u
const DEELZINSGRENS = /,\s+/g

function waardeVan(ruw) {
  if (GEGROEPEERD.test(ruw)) return Number(ruw.replace(/[.   ]/g, '').replace(',', '.'))
  return Number(ruw.replace(',', '.'))
}

/** Elk getal in een tekst, in Nederlandse notatie: { waarde, ruw, start, eind }. */
function tokens(tekst) {
  return [...tekst.matchAll(GETAL)].map(m => ({
    waarde: waardeVan(m[0]), ruw: m[0], start: m.index, eind: m.index + m[0].length,
  }))
}

function cellen(regel) {
  return regel.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim())
}

/**
 * Het antwoord als zinnen, lijstitems en tabelcellen, elk met zijn kop: { tekst, kop }.
 * Een tabelcel wordt "<rijlabel> <kolomkop>: <cel>", zodat jaar en instelling uit rij of
 * kolom bij de waarde staan.
 */
export function segmenten(tekst) {
  const regels = String(tekst ?? '').split(/\r?\n/)
  const uit = []
  let kop = ''        // laatste gewone regel: kop voor de lijst of tabel eronder
  let inleiding = ''  // gewone regel op ':', geldt voor de regels direct eronder
  let kolommen = null // kopcellen van de lopende tabel
  for (let i = 0; i < regels.length; i++) {
    const regel = regels[i]
    if (!regel.trim()) {
      inleiding = ''
      kolommen = null
      continue
    }
    if (TABELRIJ.test(regel)) {
      if (!kolommen && TABELSCHEIDING.test(regels[i + 1] ?? '')) {
        kolommen = cellen(regel)
        i++
        continue
      }
      if (kolommen) {
        const rij = cellen(regel)
        rij.forEach((cel, k) => uit.push({ tekst: k ? `${rij[0]} ${kolommen[k] ?? ''}: ${cel}` : cel, kop }))
        continue
      }
    }
    kolommen = null
    if (LIJSTITEM.test(regel) || TABELRIJ.test(regel)) {
      for (const zin of regel.replace(LIJSTITEM, '').split(ZINSGRENS)) uit.push({ tekst: zin, kop })
      continue
    }
    for (const zin of regel.split(ZINSGRENS)) uit.push({ tekst: zin, kop: inleiding })
    kop = regel
    if (regel.trim().endsWith(':')) inleiding = regel
  }
  return uit
}

/** Elk getal in het antwoord met de zin (of het lijstitem, de tabelcel) waarin het staat. */
export function getallen(tekst) {
  return segmenten(tekst).flatMap(segment => tokens(segment.tekst).map(t => ({ ...t, segment })))
}

/** Staat (een van) de term(en) in het segment of zijn kop? Geen term: geen eis. */
function noemt(segment, termen) {
  if (termen === undefined || termen === null) return true
  const tekst = `${segment.tekst} ${segment.kop}`.toLowerCase()
  return [termen].flat().some(t => tekst.includes(String(t).toLowerCase()))
}

function afstand(a, b) {
  return Math.max(0, b.start - a.eind, a.start - b.eind)
}

function deelzin(tekst, positie) {
  return [...tekst.matchAll(DEELZINSGRENS)].filter(m => m.index < positie).length
}

/**
 * Het jaar waar een getal bij hoort: een jaar in zijn eigen deelzin, anders een in de zin. De
 * volgorde van de zin beslist de richting: "2022: 30.280, 2023: 29.941" (jaar eerst) bindt aan
 * het jaar ervóór, "30.280 in 2022, 29.941 in 2023 en 29.620 in 2024" aan het jaar erna. Daarbinnen
 * wint het dichtstbijzijnde jaar.
 */
function jaarVan(getal, jaren, tekst, waardeEerst) {
  const eigen = jaren.filter(j => deelzin(tekst, j.start) === deelzin(tekst, getal.start))
  const kandidaten = eigen.length ? eigen : jaren
  const inRichting = kandidaten.filter(j => (waardeEerst ? j.start > getal.start : j.start < getal.start))
  const pool = inRichting.length ? inRichting : kandidaten
  return [...pool].sort((a, b) => afstand(getal, a) - afstand(getal, b))[0]?.ruw ?? null
}

/**
 * De getallen in het antwoord die bij `sleutel` horen. Een sleutel die een jaar is, bindt aan
 * het jaar in de tekst; de andere jaren uit `sleutels` dingen mee. Een andere sleutel ("totaal")
 * bindt alleen aan instelling en maat.
 */
export function gebondenWaarden(content, { sleutel, sleutels = [sleutel], entiteit, maat } = {}) {
  const jaren = sleutels.map(String).filter(s => JAAR.test(s))
  const bindtAanJaar = JAAR.test(String(sleutel))
  const uit = []
  for (const segment of segmenten(content)) {
    if (!noemt(segment, entiteit) || !noemt(segment, maat)) continue
    const alle = tokens(segment.tekst)
    const jaartokens = alle.filter(t => jaren.includes(t.ruw))
    const waarden = alle.filter(t => !jaren.includes(t.ruw))
    const waardeEerst = waarden.length > 0 && jaartokens.length > 0 && waarden[0].start < jaartokens[0].start
    for (const getal of waarden) {
      const hoortErbij = !bindtAanJaar || jaarVan(getal, jaartokens, segment.tekst, waardeEerst) === String(sleutel)
      if (hoortErbij) uit.push(getal.waarde)
    }
  }
  return uit
}

/**
 * 'exact' als het eindantwoord de verwachte waarde bij haar sleutel noemt, 'close' als er
 * alleen een gebonden getal binnen de tolerantie staat (informatief, geen bewijs), anders
 * 'missing'. De referentiewaarde van een andere sleutel (`anderen`) bij deze sleutel is een
 * verkeerde associatie, geen benadering: die blijft 'missing'.
 */
export function waardeInAntwoord(content, { verwacht, tolerantie = 0, anderen = [], ...context }) {
  if (verwacht === undefined || verwacht === null) return 'missing'
  const waarden = gebondenWaarden(content, context)
  if (waarden.some(w => w === verwacht)) return 'exact'
  const benaderd = w => !anderen.includes(w) && Math.abs(w - verwacht) <= Math.abs(verwacht) * tolerantie
  return waarden.some(benaderd) ? 'close' : 'missing'
}

/** Gaf een tool de verwachte waarde terug? Kaal, Engels of Nederlands genoteerd. */
export function waardeInBron(toolOutputs, verwacht) {
  if (verwacht === undefined || verwacht === null) return false
  return toolOutputs.some(uitvoer => [...String(uitvoer ?? '').matchAll(BRONGETAL)].some(m => {
    const ruw = m[0]
    const lezingen = [waardeVan(ruw), Number(ruw), Number(ruw.replace(/,/g, '')), ...ruw.split(',').map(Number)]
    return lezingen.includes(verwacht)
  }))
}

/**
 * Noemt het antwoord bij een sleutel een getal dat niet de referentiewaarde is? Jaartallen
 * tellen niet als waarde.
 */
export function tegenspreekt(content, dataPoints) {
  const referenties = dataPoints?.reference_values
  if (!referenties) return false
  const sleutels = Object.keys(referenties)
  return Object.entries(referenties).some(([sleutel, verwacht]) => {
    const context = { sleutel, sleutels, entiteit: dataPoints.entity, maat: dataPoints.maat }
    const waarden = gebondenWaarden(content, context).filter(w => !JAAR.test(String(w)))
    return waarden.length > 0 && !waarden.includes(verwacht)
  })
}
