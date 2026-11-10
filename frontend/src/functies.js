import { VASTE_BRONNEN, bronnamen } from './bronnenLijst'

// De functies om uit te kiezen in de instellingen (#591). De gekozen functie gaat ook als context mee naar
// de server (chatSettings in ChatPage). "Anders" is een keuze, geen functienaam: die komt niet in een zin.
export const FUNCTIES = ['Bestuurder', 'Directeur', 'Beleidsmedewerker', 'IR-specialist', 'Onderzoeker', 'Docent', 'Anders']

const ROLLEN = new Set(FUNCTIES.filter(f => f !== 'Anders'))

// Zonder functie noemt de zin de bronnen van deze omgeving (bronnenLijst.js, #1006). Niet "open data": de
// Studiekeuzedatabase is gelicentieerd.
const zonderRol = bronnen => 'Vraag wat je wilt weten over instroom, voortgang, arbeidsmarkt of diplomering. Ik geef je ' +
  `een onderbouwd antwoord met data van ${bronnamen(bronnen)}.`

export const isFunctie = functie => FUNCTIES.includes(functie)

// Een functietitel met kleine letter midden in de zin; een afkorting als "IR-specialist" houdt haar hoofdletters.
const inZin = functie => (functie.startsWith('IR-') ? functie : functie.toLowerCase())

// De tweede regel van het welkomstscherm. Een functietitel staat midden in de zin met een kleine letter; een
// onbekende waarde (een oudere opgeslagen instelling) of "Anders" geeft de zin zonder functie, met de bronnen.
export function welkomstSub(functie, bronnen = VASTE_BRONNEN) {
  if (!ROLLEN.has(functie)) return zonderRol(bronnen)
  return `Als ${inZin(functie)} krijg je onderbouwde antwoorden over instroom, voortgang, arbeidsmarkt en ` +
    'diplomering — direct uit open onderwijsdata.'
}
