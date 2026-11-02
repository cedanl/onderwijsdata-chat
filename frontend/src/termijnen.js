import { useSyncExternalStore } from 'react'

// De bewaartermijnen en de sessieduur die de backend toepast (#835): /api/config geeft ze mee
// (BEWAARTERMIJN_GESPREKKEN_DAGEN, BEWAARTERMIJN_RAPPORTEN_DAGEN, SESSION_TTL_HOURS, SESSION_MAX_HOURS). Deze
// standaarden zijn de backenddefaults; ze gelden tot /api/config antwoordt, en voor een waarde die ontbreekt.
// De feedback volgt de termijn van de gesprekken (persistence/opschonen.py).
export const STANDAARD_TERMIJNEN = Object.freeze({ gesprekkenDagen: 90, rapportenDagen: 365, sessieUren: 8, sessieMaxUren: 24 })

const positief = (waarde, terugval) => (typeof waarde === 'number' && Number.isFinite(waarde) && waarde > 0 ? waarde : terugval)

let huidig = STANDAARD_TERMIJNEN
const luisteraars = new Set()

export function zetTermijnen(config) {
  const s = STANDAARD_TERMIJNEN
  huidig = Object.freeze({
    gesprekkenDagen: positief(config?.bewaartermijn_gesprekken_dagen, s.gesprekkenDagen),
    rapportenDagen: positief(config?.bewaartermijn_rapporten_dagen, s.rapportenDagen),
    sessieUren: positief(config?.sessie_uren, s.sessieUren),
    sessieMaxUren: positief(config?.sessie_max_uren, s.sessieMaxUren),
  })
  luisteraars.forEach(l => l())
}

function abonneer(luisteraar) {
  luisteraars.add(luisteraar)
  return () => luisteraars.delete(luisteraar)
}

export function useTermijnen() {
  return useSyncExternalStore(abonneer, () => huidig, () => STANDAARD_TERMIJNEN)
}

// Een getal in de tekst, in Nederlandse notatie (een halve dag of uur als 0,5).
export const getal = n => n.toLocaleString('nl-NL')
