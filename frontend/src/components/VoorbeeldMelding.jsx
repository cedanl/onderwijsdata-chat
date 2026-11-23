// De vaste dashboards rekenen zonder gekozen instelling met de voorbeeldinstelling (#1098). Dit zegt dat, en de knop opent
// Instellingen. Zonder `onKies` (de pagina kan Instellingen niet openen) blijft alleen de uitleg.
export default function VoorbeeldMelding({ instelling, onKies }) {
  return (
    <div className="wb-gallery-notice db-voorbeeld">
      <strong>{instelling}</strong> is een voorbeeld: je hebt nog geen instelling gekozen. Kies je eigen instelling om de
      cijfers van jouw instelling te zien.
      {onKies && <button type="button" className="wb-gallery-notice-actie" onClick={onKies}>Kies je instelling</button>}
    </div>
  )
}
