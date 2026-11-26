// De regel "Wat is gecontroleerd" onder een data-antwoord (#1260), uit het veld `controles` van message_end
// (agent/controleoverzicht.py). Alleen tellingen uit code: wat het model over zijn eigen controle schrijft, verandert
// de regel niet. Ze zegt altijd ook wat níét getoetst is: de vaste zin hieronder, gelijk aan "Wat dit niet dekt" in
// docs/anti-hallucination-architecture.md (tests/test_controleoverzicht.py houdt ze gelijk). Geen vinkje en geen woord
// dat meer belooft dan de controle doet.

export const NIET_GECONTROLEERD = 'Niet gecontroleerd: of de bron zelf klopt, getallen onder de duizend en jaartallen, conclusies en verbanden die niet uit de cijfers volgen, en bij welke groep een getal hoort als de zin of tabelrij geen jaar of instelling noemt.'
export const GEEN_GETALLEN = 'Geen getallen om te controleren'
export const KOP = 'Wat is gecontroleerd'

const aantal = waarde => (Number.isInteger(waarde) && waarde > 0 ? waarde : 0)
const keer = n => (n === 1 ? 'één keer' : `${n} keer`)

function correctieZin(ingetrokken, gecorrigeerd) {
  const totaal = ingetrokken + gecorrigeerd
  if (!totaal) return null
  const delen = [
    ingetrokken && `${keer(ingetrokken)} ingetrokken en opnieuw geschreven`,
    gecorrigeerd && `${keer(gecorrigeerd)} zinnen met een getal dat niet in de data staat weggelaten`,
  ].filter(Boolean)
  return `Na de controle ${totaal === 1 ? 'één correctie' : `${totaal} correcties`}: ${delen.join(', ')}.`
}

// { kop, details } voor de regel, of null zonder (geldig) veld: een bericht van vóór #1260 krijgt geen regel.
export function controleSamenvatting(controles) {
  if (!controles || typeof controles !== 'object' || Array.isArray(controles)) return null
  const getallen = aantal(controles.getallen)
  const gebonden = aantal(controles.gebonden)
  const nietGedraaid = aantal(controles.niet_gedraaid)
  const kop = getallen
    ? `${getallen} ${getallen === 1 ? 'getal' : 'getallen'} tegen de opgehaalde data gelegd`
    : GEEN_GETALLEN
  const details = [
    gebonden > 0 && `${gebonden} ${gebonden === 1 ? 'getal' : 'getallen'} met vastgestelde herkomst: de cel in de data waar het staat.`,
    getallen > 0 && (controles.jaar_en_instelling === true
      ? 'Schooljaar en instelling bij de getallen nagelopen tegen de opgehaalde selectie.'
      : 'Schooljaar en instelling bij de getallen niet volledig nagelopen.'),
    nietGedraaid > 0 && `${nietGedraaid} ${nietGedraaid === 1 ? 'controle kon' : 'controles konden'} niet draaien; daar is de tekst niet aan de data getoetst.`,
    correctieZin(aantal(controles.ingetrokken), aantal(controles.gecorrigeerd)),
  ].filter(Boolean)
  return { kop, details }
}

// De regel als platte tekst, voor kopie, gespreksexport en CSV-kop (#1257, #1260): kop, details en de vaste zin.
// Een leeg veld geeft ''.
export function controleRegelTekst(controles) {
  const samenvatting = controleSamenvatting(controles)
  if (!samenvatting) return ''
  return [`${KOP}: ${samenvatting.kop}.`, ...samenvatting.details, NIET_GECONTROLEERD].join(' ')
}

const isObject = waarde => typeof waarde === 'object' && waarde !== null && !Array.isArray(waarde)

// Per controle alleen `gedraaid` (ja/nee) en `uitkomst` (tekst), zoals agent/controleoverzicht.py ze zet.
function perControle(waarde) {
  if (!isObject(waarde)) return {}
  return Object.fromEntries(Object.entries(waarde)
    .filter(([, c]) => isObject(c) && typeof c.gedraaid === 'boolean' && typeof c.uitkomst === 'string')
    .map(([naam, c]) => [naam, { gedraaid: c.gedraaid, uitkomst: c.uitkomst }]))
}

// De sleutel `controles` van het bewijsbestand (#1244, #1260): de regel zoals hierboven, met de tellingen uit code
// waar ze op rust. Alleen de bekende sleutels gaan mee, wat er verder in een bewaard bericht staat niet; zonder
// (geldig) veld null, zoals elke sleutel van het bewijs die niet van toepassing is.
export function controlesVoorBewijs(controles) {
  const regel = controleRegelTekst(controles)
  if (!regel) return null
  return {
    regel,
    per_controle: perControle(controles.per_controle),
    getallen: aantal(controles.getallen),
    gebonden: aantal(controles.gebonden),
    jaar_en_instelling: controles.jaar_en_instelling === true,
    niet_gedraaid: aantal(controles.niet_gedraaid),
    ingetrokken: aantal(controles.ingetrokken),
    gecorrigeerd: aantal(controles.gecorrigeerd),
  }
}
