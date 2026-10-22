import FiguurTabel from './FiguurTabel'

// De waarden onder een grafiek, standaard ingeklapt (#664): op een telefoon is een tooltip de enige weg naar een
// waarde, en een schermlezer kreeg per reeks alleen de eerste en laatste (#588).
export default function WaardenTabel({ tabel }) {
  return (
    <details className="waarden-details">
      <summary>Toon de waarden</summary>
      <FiguurTabel tabel={tabel} />
    </details>
  )
}
