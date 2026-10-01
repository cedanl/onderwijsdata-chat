import { Link } from 'react-router-dom'

// An unknown path says so (404); a page that exists but is switched off says that
// instead, so a followed link is never mistaken for a typo (#223).
export default function NotFoundPage({ unavailable = false }) {
  return (
    <div className="notfound" role="alert">
      <h1>{unavailable ? 'Nog niet beschikbaar' : 'Deze pagina bestaat niet (meer)'}</h1>
      <p>
        {unavailable
          ? 'Deze functie staat op dit moment uit. De link is wel goed: probeer het later opnieuw.'
          : 'Controleer de link, of ga terug naar de startpagina.'}
      </p>
      <Link to="/" className="notfound-link">Terug naar de startpagina</Link>
    </div>
  )
}
