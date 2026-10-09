// De vaste bouwstenen onder een dataantwoord (#416, CH-09). Vijf keer dezelfde vraag gaf 0 of 9
// citaties, 3 of 4 CSV-knoppen en wel of geen Telling-blok: wat er onder het antwoord stond,
// verschilde per run. Het aantal items volgt de tekst en de stappen; welke blokken er staan en
// in welke volgorde, staat hier vast. Een blok zonder inhoud zegt "n.v.t." in plaats van te ontbreken.
import { exportKeys } from './dataExport'
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
export function answerBlocks(msg, { settled = false } = {}) {
  if (!isDataAnswer(msg, settled)) return null
  const gevuld = {
    citaties: msg.citaties?.length > 0,
    telling: Boolean(splitsTelling(msg.content).telling),
    export: exportKeys(msg.tools).length > 0,
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
