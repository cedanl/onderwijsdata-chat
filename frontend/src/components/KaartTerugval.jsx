import FiguurTabel from './FiguurTabel'
import { figuurTabel } from '../figuurTabel'

// Wat de chat toont als een kaart niet getekend is (#632): een melding en de cijfers van de kaart als tabel. De
// dashboardkaart geeft haar eigen tabel mee (#906).
export default function KaartTerugval({ figure, tabel = figuurTabel(figure) }) {
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
