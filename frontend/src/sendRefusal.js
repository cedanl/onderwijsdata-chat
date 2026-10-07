// Waarom useChat.send() een vraag weigerde, als zichtbare melding (#241).
// Zonder melding bleef de tekst stil in het invoerveld staan en leek de app te hangen.
export function sendRefusalReason({ connected, busy, resetting, reporting = false }) {
  if (busy) return 'Er loopt nog een vraag. Wacht tot die klaar is, of stop hem eerst.'
  if (reporting) return 'Er wordt nog een rapport gemaakt. Wacht tot het klaar is, of annuleer het eerst.'
  if (resetting) return 'Het nieuwe gesprek wordt nog gestart. Probeer het zo opnieuw.'
  if (!connected) return 'Geen verbinding met de server. Je vraag blijft staan; verstuur hem opnieuw zodra de verbinding terug is.'
  return 'Je vraag kon niet worden verstuurd. Probeer het opnieuw.'
}
