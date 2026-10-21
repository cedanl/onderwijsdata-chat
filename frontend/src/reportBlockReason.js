// Waarom "Genereer rapport" nu niet kan starten, als één korte reden (#648). Een tik zonder reden en zonder rapport
// leek een kapotte knop. Dezelfde woorden als bij een vraag (sendBlockReason.js) voor wat bij beide speelt; wat
// vanzelf overgaat, begint met "Even wachten:".
const REDENEN = {
  reporting: 'Er wordt al een rapport gemaakt',
  open: 'Wacht tot het antwoord klaar is',
  resetting: 'Even wachten: het nieuwe gesprek wordt gestart',
  // Na de herverbinding start het rapport niet vanzelf: de gebruiker tikt opnieuw.
  offline: 'Geen verbinding: tik opnieuw zodra de verbinding terug is',
}

const reden = key => ({ key, text: REDENEN[key] })

// { key, text } of null als het rapport kan starten. `open`: er loopt nog een antwoord (ook vóór zijn eerste tekst).
export function reportBlockReason({ connected, open, reporting, resetting }) {
  if (reporting) return reden('reporting')
  if (open) return reden('open')
  if (resetting) return reden('resetting')
  if (!connected) return reden('offline')
  return null
}
