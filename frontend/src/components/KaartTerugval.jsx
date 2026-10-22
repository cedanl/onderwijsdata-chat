import FiguurTabel from './FiguurTabel'
import { figuurTabel } from '../figuurTabel'

// Wat de chat toont als een kaart niet getekend is (#632): een melding en de cijfers van de kaart als tabel.
export default function KaartTerugval({ figure }) {
  const tabel = figuurTabel(figure)
  const titel = figure?.layout?.title?.text
  return (
    <>
      <div role="alert" className="kaart-mislukt">
        De kaart kon niet worden getekend.{' '}
        {tabel ? 'De cijfers staan in de tabel hieronder.' : 'Controleer de cijfers in het antwoord.'}
      </div>
      {tabel && <FiguurTabel tabel={tabel} titel={titel} />}
    </>
  )
}
