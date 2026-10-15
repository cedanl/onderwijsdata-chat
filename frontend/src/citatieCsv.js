// De cijfers die een antwoord citeert, als CSV (#544).
//
// De server noemt alleen een tabel-key voor een stap die een selectie in de store legde
// (query_data, run_analysis, get_maat). Een antwoord dat zijn tabel uit compute_kpi of uit
// de eerste rijen van een bronbestand haalde, heeft wél citaties (agent/citaties.py) maar
// geen tabel-key: dan ontbrak de CSV-knop, afhankelijk van welke tool het model koos. De
// citaties zijn de data achter zo'n antwoord: per gecontroleerd getal de maat, de selectie
// en de bron, in de volgorde van de tekst. Zelfde opmaak als de grafiekexport: puntkomma,
// '#'-regels erboven (#118), tekst die Excel als formule zou lezen krijgt een ' (#483).

import { toCsv } from './figureCsv'

const KOLOMMEN = ['getal', 'maat', 'eenheid', 'selectie', 'bron', 'stap']

// Alleen getallen met vastgestelde herkomst: een getal zonder herkomst hoort niet in een
// bestand dat "de data achter het antwoord" heet.
export function citatieRijen(citaties) {
  return Array.isArray(citaties) ? citaties.filter(c => c && c.vastgesteld === true) : []
}

export function citatiesToCsv(citaties) {
  const rijen = citatieRijen(citaties)
  if (!rijen.length) return null
  const weggelaten = citaties.length - rijen.length
  const noten = ['cijfers uit het antwoord, zoals geschreven, met de herkomst per getal']
  if (weggelaten > 0) {
    noten.push(`${weggelaten} ${weggelaten === 1 ? 'getal' : 'getallen'} zonder vastgestelde herkomst weggelaten`)
  }
  const body = toCsv([KOLOMMEN, ...rijen.map(c => [c.getal, c.maat, c.eenheid, c.selectie, c.bron, c.stap])])
  return [...noten.map(n => `# ${n}`), body].join('\n')
}

export const CITATIE_CSV_BESTAND = 'cijfers_antwoord.csv'
