import TabelScroll from './TabelScroll'
import { isRij } from '../figureCsv'

const GETAL = new Intl.NumberFormat('nl-NL')

// De rijen van een kaart als tabel: de server geeft ze mee in layout.meta (create_choropleth_map, #217).
function kaartTabel(figure) {
  const { data, location_col: plek, value_col: waarde } = figure?.layout?.meta ?? {}
  if (!Array.isArray(data) || !plek || !waarde) return null
  // Alleen rijen als object: een kapotte of oude meta (een lijst, null) liet de tabel anders vallen (#642).
  const rijen = data.filter(isRij).map(rij => [rij[plek], rij[waarde]])
  return rijen.length ? { kolommen: [plek, waarde], rijen } : null
}

const cel = waarde => (typeof waarde === 'number' ? GETAL.format(waarde) : String(waarde ?? ''))

// Wat de chat toont als een kaart niet getekend is (#632): een melding en de cijfers van de kaart als tabel.
export default function KaartTerugval({ figure }) {
  const tabel = kaartTabel(figure)
  const titel = figure?.layout?.title?.text
  return (
    <>
      <div role="alert" className="kaart-mislukt">
        De kaart kon niet worden getekend.{' '}
        {tabel ? 'De cijfers staan in de tabel hieronder.' : 'Controleer de cijfers in het antwoord.'}
      </div>
      {tabel && (
        <TabelScroll className="kaart-tabel">
          {titel && <caption>{titel}</caption>}
          <thead>
            <tr>{tabel.kolommen.map(k => <th key={k} scope="col">{k}</th>)}</tr>
          </thead>
          <tbody>
            {tabel.rijen.map(([plek, waarde], i) => (
              <tr key={`${plek}-${i}`}><td>{cel(plek)}</td><td>{cel(waarde)}</td></tr>
            ))}
          </tbody>
        </TabelScroll>
      )}
    </>
  )
}
