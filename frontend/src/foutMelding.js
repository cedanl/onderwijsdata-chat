// Wat de gebruiker leest als een verzoek in een dialoog mislukt (#1131). api.js maakt van een mislukt verzoek een Error
// met de tekst van de server (`error` of `detail`, voor gebruikers geschreven), of anders "API 500" of "Unauthorized";
// een netwerkfout is de TypeError "Failed to fetch". Die ruwe teksten zijn Engels, dragen een statuscode en zeggen niet
// wat je kunt doen: ze komen niet in beeld.
const API_STATUS = /^API \d+$/

const eigenTekst = err => typeof err.message === 'string' && err.message !== '' && !API_STATUS.test(err.message)

// `wat` is de zin die zegt wat er niet lukte, zonder punt: "Feedback niet verstuurd".
export function foutMelding(wat, err) {
  // Een tekst die de server voor de gebruiker schreef (bijvoorbeeld "Een grafiek is groter dan 2 MiB") blijft zichtbaar.
  if (err?.status && err.status !== 401 && eigenTekst(err)) return `${wat}: ${err.message}`
  if (err?.status === 401) return `${wat}. Je sessie is verlopen; log opnieuw in en probeer het nog eens.`
  if (err?.status || err instanceof SyntaxError) return `${wat}. De server kon het niet verwerken; probeer het over een minuut opnieuw.`
  if (err instanceof TypeError) return `${wat}. De server is niet bereikbaar; controleer je verbinding en probeer het opnieuw.`
  // Een fout uit onze eigen code, zonder status, met een eigen Nederlandse tekst.
  return eigenTekst(err ?? {}) ? `${wat}: ${err.message}` : `${wat}. Probeer het opnieuw.`
}
