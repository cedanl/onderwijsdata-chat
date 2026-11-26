// De vaste bouwstenen onder een dataantwoord (#416, CH-09). Vijf keer dezelfde vraag gaf 0 of 9
// citaties, 3 of 4 CSV-knoppen en wel of geen Telling-blok: wat er onder het antwoord stond,
// verschilde per run. Het aantal items volgt de tekst en de stappen; welke blokken er staan en
// in welke volgorde, staat hier vast. Een blok zonder inhoud zegt "n.v.t." in plaats van te ontbreken.
import { controleRegelTekst } from './controleRegel'
import { actualiteitRegels } from './voorbehoud'
import { hasExport } from './dataExport'
import { splitsTelling } from './telling'

export const BLOKKEN = ['citaties', 'telling', 'export', 'bronnen']
export const AANWEZIG = 'aanwezig'
export const NVT = 'n.v.t.'

// Alleen de bronnen die tekst zijn: een bericht uit localStorage of de gespreksopslag kan er iets
// anders in hebben, en React kan een object niet tonen.
export function bronnenTekst(bronnen) {
  return Array.isArray(bronnen) ? bronnen.filter(b => typeof b === 'string' && b.trim()) : []
}

// Een dataantwoord: klaar, geen fout, met de bronnenlijst van de server (een bericht van vóór #416
// heeft er geen; dan geen valse "n.v.t.") en met data erachter. Ingehouden, geweigerd of leeg: de
// server stuurt dan een lege lijst en er zijn geen citaties.
function isDataAnswer(msg, settled) {
  if (!settled || !msg || msg.isError || !Array.isArray(msg.bronnen)) return false
  return bronnenTekst(msg.bronnen).length > 0 || msg.citaties?.length > 0
}

// De blokken in vaste volgorde, elk aanwezig of n.v.t.; null voor elk ander bericht, dat blijft zoals het was.
// geavanceerd: of de CSV-downloads te zien zijn (#1269); Message geeft de stand mee, zonder opgave tellen ze mee.
export function answerBlocks(msg, { settled = false, geavanceerd = true } = {}) {
  if (!isDataAnswer(msg, settled)) return null
  const gevuld = {
    citaties: msg.citaties?.length > 0,
    telling: Boolean(splitsTelling(msg.content).telling),
    // Een dataantwoord heeft altijd zijn bewijsbestand (#1244, bewijsJson.js), naast de CSV als die er is; een vast
    // antwoord uit code (#565) niet.
    export: (geavanceerd && hasExport(msg)) || msg.vast !== true,
    bronnen: bronnenTekst(msg.bronnen).length > 0,
  }
  return BLOKKEN.map(kind => ({ kind, status: gevuld[kind] ? AANWEZIG : NVT }))
}

// "9 getallen met herkomst", of hoeveel daarvan geen vastgestelde herkomst hebben (agent/citaties.py).
export function citatieSamenvatting(citaties = []) {
  const n = citaties.length
  const onbepaald = citaties.filter(c => c.vastgesteld === false).length
  const getallen = `${n} ${n === 1 ? 'getal' : 'getallen'}`
  return onbepaald > 0 ? `${getallen}, waarvan ${onbepaald} zonder vastgestelde herkomst` : `${getallen} met herkomst`
}

// De bronnen als markdown, voor kopiëren en de gespreksexport: de server haalde de eigen
// Bronnen-sectie van het model uit de tekst, dus anders gingen ze daar verloren.
export function bronnenMarkdown(bronnen) {
  const lijst = bronnenTekst(bronnen)
  return lijst.length ? ['**Bronnen**', ...lijst.map(b => `- ${b}`)].join('\n') : ''
}

// De tekst van een antwoord met de bronnen eronder.
export function metBronnen(content, bronnen) {
  const lijst = bronnenMarkdown(bronnen)
  return lijst && content ? `${content}\n\n${lijst}` : content
}

// Wat onder de tekst van een antwoord hoort, voor kopie en gespreksexport (#1257): elke controlemelding als
// "Let op: …" (zoals onder het antwoord, #1108) en de regel "Wat is gecontroleerd" met wat níét getoetst is (#1260).
// Het Uitgangspunt, "Niet meegeteld" en "Bron en definitie" staan al in de tekst zelf (agent/run.py).
export function meldingRegels(msg) {
  const regel = controleRegelTekst(msg.controles)
  return [...(msg.controle || []).map(zin => `Let op: ${zin}`), ...actualiteitRegels(msg), ...(regel ? [regel] : [])]
}

// Wat de kopieerknop meeneemt: het antwoord, de meldingen hierboven en dan de bronnen. Zonder die regels zegt de
// kopie niet dat de controle iets uit het antwoord haalde (#1108), of wat ze niet toetste (#1260).
export function kopieerTekst(msg) {
  const meldingen = meldingRegels(msg)
  return metBronnen(meldingen.length ? [msg.content, ...meldingen].join('\n\n') : msg.content, msg.bronnen)
}
