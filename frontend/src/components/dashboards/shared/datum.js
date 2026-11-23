// Eén datumnotatie op de dashboards (#1143): dag, maand voluit, jaar: "16 mei 2023". De backend geeft datums zoals de
// bron ze heeft (ISO "2023-05-16", "08-04-2026" van DUO, een tijdstip van het ophalen); de frontend zet ze hier om.

const LANG = { day: 'numeric', month: 'long', year: 'numeric' }
const DAG = new Intl.DateTimeFormat('nl-NL', { ...LANG, timeZone: 'UTC' })
const MOMENT = new Intl.DateTimeFormat('nl-NL', LANG)

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/
const NL = /^(\d{2})-(\d{2})-(\d{4})$/
const TIJDSTIP = /^\d{4}-\d{2}-\d{2}T/

const dag = (jaar, maand, dagnr) => DAG.format(new Date(Date.UTC(Number(jaar), Number(maand) - 1, Number(dagnr))))

// "2023-05-16" of "16-05-2023" → "16 mei 2023"; een tijdstip ("2026-11-20T10:15:00") → de datum ervan; iets anders
// (zoals "1 oktober" of "onbekend") ongewijzigd.
export function langeDatum(waarde) {
  const tekst = String(waarde ?? '').trim()
  const iso = tekst.match(ISO)
  if (iso) return dag(iso[1], iso[2], iso[3])
  const nl = tekst.match(NL)
  if (nl) return dag(nl[3], nl[2], nl[1])
  if (TIJDSTIP.test(tekst) && !Number.isNaN(new Date(tekst).getTime())) return MOMENT.format(new Date(tekst))
  return tekst
}

// Elke datum midden in een tekst ("versie van 08-04-2026", "peildatum 2023-05-16") in dezelfde notatie.
export function datumsInTekst(tekst) {
  return String(tekst ?? '').replace(/\b(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})\b/g, d => langeDatum(d))
}
