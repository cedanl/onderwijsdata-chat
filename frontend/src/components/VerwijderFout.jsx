// Een rapport of dashboard dat de server nog heeft omdat de DELETE niet lukte (#778): het staat weer in de galerij,
// en hier kan het meteen opnieuw. `fout` komt uit useWorkbookGallery.
export default function VerwijderFout({ fout }) {
  if (!fout) return null
  return (
    <div className="wb-gallery-notice" role="alert">
      {fout.titel ? `"${fout.titel}" verwijderen` : 'Verwijderen'} is niet gelukt. Het staat weer in de lijst.
      <button type="button" className="wb-gallery-notice-actie" onClick={fout.opnieuw}>Opnieuw proberen</button>
    </div>
  )
}
