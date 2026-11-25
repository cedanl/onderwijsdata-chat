import TabelScroll from './TabelScroll'

// signDisplay 'negative': een waarde die op nul afrondt (-0, -0,0004) toont als "0", nooit als "-0" (#1101).
const GETAL = new Intl.NumberFormat('nl-NL', { signDisplay: 'negative' })

// Een waarde als getal in Nederlandse notatie; een label (x, reeks) blijft zoals het staat: 2020 is geen 2.020. Een
// waarde waarin een onderdrukte cel valt, is een ondergrens: "≥ 1.234" (#1261), zoals de hover "ten minste" zegt.
function cel(waarde, isLabel, ondergrens) {
  if (typeof waarde !== 'number' || isLabel) return String(waarde ?? '')
  return ondergrens ? `≥ ${GETAL.format(waarde)}` : GETAL.format(waarde)
}

// De tabel uit figuurTabel.js (#664), ook die van een kaart die niet getekend is (#632).
export default function FiguurTabel({ tabel, titel }) {
  return (
    <TabelScroll className="figuur-tabel">
      {titel && <caption>{titel}</caption>}
      <thead>
        <tr>{tabel.kolommen.map((k, i) => <th key={i} scope="col" className={i < tabel.labels ? undefined : 'getal'}>{k}</th>)}</tr>
      </thead>
      <tbody>
        {tabel.rijen.map((rij, r) => (
          <tr key={r}>
            {rij.map((waarde, i) => (
              <td key={i} className={i < tabel.labels ? undefined : 'getal'}>
                {cel(waarde, i < tabel.labels, tabel.ondergrens?.has(`${r}:${i}`))}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </TabelScroll>
  )
}
