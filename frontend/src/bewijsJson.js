// "Bewijs (JSON)" bij een dataantwoord (#1244): wat het bericht al over zijn herkomst weet, in één bestand. Gebouwd
// hier, uit het bericht zelf: geen API-route en geen modelaanroep. Een heropend gesprek geeft daardoor hetzelfde
// bestand, want elk veld staat in het bewaarde bericht (de toolargumenten sinds #1244, zie useChat.js).
//
// Wel: het manifest (model, versies, dataversie), de bronnen met hun links, de citaties, de controlemeldingen, per
// geslaagde stap de tool, haar argumenten en de code die haar herhaalt, het label "Vaste maat" en het antwoord.
// Niet: de ruwe uitvoer van een tool, de vraag, de gebruikersnaam. Een sleutel die niet van toepassing is, is null.
import { bronnenTekst } from './answerBlocks'
import { bestandsdeel } from './bestandsnaam'
import { zijnBronlinks } from './bronLink'
import { conversationTitle } from './conversationTitle'
import { vasteMaat } from './vasteMaat'

export const BEWIJS_SCHEMA = 'onderwijsdata-chat/bewijs/1'
export const BEWIJS_SLEUTELS = [
  'schema', 'manifest', 'bronnen', 'bronlinks', 'citaties', 'controle', 'toolstappen', 'vaste_maat', 'antwoord',
]

const isObject = waarde => typeof waarde === 'object' && waarde !== null && !Array.isArray(waarde)
const lijstOfNull = lijst => (lijst.length ? lijst : null)
const tekstOfNull = waarde => (typeof waarde === 'string' && waarde.trim() ? waarde : null)
// Mislukt, leeg, door de scopegrens geweigerd of gestopt: geen stap waar het antwoord op rust.
const geslaagd = stap => isObject(stap) && stap.done !== false && !stap.status && typeof stap.name === 'string'

// Per stap alleen naam, argumenten en code: nooit de uitvoer van de tool, ook niet als een bericht die zou dragen.
function toolstappen(tools) {
  const stappen = (Array.isArray(tools) ? tools : []).filter(geslaagd).map(stap => ({
    name: stap.name,
    arguments: isObject(stap.arguments) ? stap.arguments : null,
    snippet: tekstOfNull(stap.snippet),
  }))
  return lijstOfNull(stappen)
}

// Of een bericht een bewijsbestand krijgt: een dataantwoord, met bronnen, citaties of een vaste maat. Een vast
// antwoord uit code (#565) of een fout rust niet op data en krijgt er geen.
export function heeftBewijs(msg) {
  if (!isObject(msg) || msg.isError || msg.vast === true) return false
  return bronnenTekst(msg.bronnen).length > 0 || (Array.isArray(msg.citaties) && msg.citaties.length > 0) ||
    vasteMaat(msg.vaste_maat) !== null
}

// Het bewijs als object, in vaste sleutelvolgorde.
export function bewijs(msg) {
  return {
    schema: BEWIJS_SCHEMA,
    manifest: isObject(msg.manifest) && msg.manifest.model ? msg.manifest : null,
    bronnen: lijstOfNull(bronnenTekst(msg.bronnen)),
    bronlinks: zijnBronlinks(msg.bronlinks) && Object.keys(msg.bronlinks).length ? msg.bronlinks : null,
    citaties: lijstOfNull(Array.isArray(msg.citaties) ? msg.citaties.filter(isObject) : []),
    controle: lijstOfNull(Array.isArray(msg.controle) ? msg.controle.filter(z => typeof z === 'string') : []),
    toolstappen: toolstappen(msg.tools),
    vaste_maat: vasteMaat(msg.vaste_maat),
    antwoord: tekstOfNull(msg.content),
  }
}

export const bewijsJson = msg => JSON.stringify(bewijs(msg), null, 2) + '\n'

// De bestandsnaam: dezelfde regel als de gespreksexport (#478). De titel uit de vraag, maar een vraag met een BSN,
// e-mailadres of telefoonnummer geeft de generieke titel; zonder vraag `bewijs_antwoord.json`.
export function bewijsBestandsnaam(vraag) {
  const deel = tekstOfNull(vraag) ? bestandsdeel(conversationTitle(vraag), 80) : ''
  return `bewijs_${deel || 'antwoord'}.json`
}
