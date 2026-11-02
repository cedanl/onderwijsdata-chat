// Een figuur als object, uit een JSON-tekst of een al geparste figuur; null bij onleesbare JSON. Grafiek in een
// antwoord, in een gegenereerd dashboard en de kaart van een dashboard lezen hun figuur zo (#836).
export function leesFiguur(figureJson) {
  try {
    return typeof figureJson === 'string' ? JSON.parse(figureJson) : figureJson
  } catch {
    return null
  }
}
