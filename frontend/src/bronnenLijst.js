import { useSyncExternalStore } from 'react'

// De bronnen die de welkomsttekst van de chat, de intro van de homepage en de privacy-informatie noemen (#1006): één
// lijst. De vaste bronnen, plus wat /api/config `bronnen` hier als aan meldt (tools/beschikbaarheid.py): de
// Studiekeuzedatabase alleen met haar sleutel, WOPI van UNL alleen met zijn vlag. `financien` is data van DUO en voegt
// geen naam toe.
// - `alleenMet`: de sleutel in /api/config `bronnen` die true moet zijn;
// - `opvraag: false`: de app vraagt daar niets op (het collegegeld staat als vaste tabel in tools/collegegeld.py);
// - `gelicentieerd`: geen open data;
// - `privacynoot`: wat de privacy-informatie over die bron zegt, naast de opsomming.
const BRONNEN = Object.freeze([
  { naam: 'CBS' },
  { naam: 'DUO' },
  { naam: 'RIO' },
  { naam: 'UWV' },
  { naam: 'ROA' },
  { naam: 'de Onderwijsinspectie' },
  {
    naam: 'de Studiekeuzedatabase (LCSK)', alleenMet: 'studiekeuze', gelicentieerd: true,
    privacynoot: 'De Studiekeuzedatabase is gelicentieerde data van LCSK, geen open data; de app vraagt haar op met een eigen sleutel.',
  },
  { naam: 'UNL (WOPI)', alleenMet: 'wo_personeel' },
  {
    naam: 'wetten.nl (collegegeld)', opvraag: false,
    privacynoot: 'Het wettelijk collegegeld staat als vaste tabel in de app, overgenomen van wetten.nl; daarheen gaat geen opvraag.',
  },
].map(Object.freeze))

// De bronnen voor deze omgeving, uit /api/config `bronnen`; alleen een echte true zet een bron aan.
export function bronnenLijst(bronnen) {
  const aan = bronnen && typeof bronnen === 'object' ? bronnen : {}
  return Object.freeze(BRONNEN.filter(b => !b.alleenMet || aan[b.alleenMet] === true))
}

// "CBS, DUO en RIO".
export const opsomming = namen => (namen.length < 2 ? (namen[0] ?? '') : `${namen.slice(0, -1).join(', ')} en ${namen.at(-1)}`)

export const bronnamen = lijst => opsomming(lijst.map(b => b.naam))

// Tot /api/config antwoordt, alleen de vaste bronnen. App zet de lijst uit dat antwoord, zodat ook /privacy vóór het
// inloggen en de popup haar zonder props lezen (zoals termijnen.js).
export const VASTE_BRONNEN = bronnenLijst({})

let huidig = VASTE_BRONNEN
const luisteraars = new Set()

export function zetBronnenLijst(bronnen) {
  huidig = bronnenLijst(bronnen)
  luisteraars.forEach(l => l())
}

function abonneer(luisteraar) {
  luisteraars.add(luisteraar)
  return () => luisteraars.delete(luisteraar)
}

export function useBronnenLijst() {
  return useSyncExternalStore(abonneer, () => huidig, () => VASTE_BRONNEN)
}
