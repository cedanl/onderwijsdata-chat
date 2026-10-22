import TabelScroll from './TabelScroll'

const GETAL = new Intl.NumberFormat('nl-NL')

// Een waarde als getal in Nederlandse notatie; een label (x, reeks) blijft zoals het staat: 2020 is geen 2.020.
const cel = (waarde, isLabel) => (typeof waarde === 'number' && !isLabel ? GETAL.format(waarde) : String(waarde ?? ''))

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
            {rij.map((waarde, i) => <td key={i} className={i < tabel.labels ? undefined : 'getal'}>{cel(waarde, i < tabel.labels)}</td>)}
          </tr>
        ))}
      </tbody>
    </TabelScroll>
  )
}
