### Rapport: een bronstoring geeft snel een foutmelding (#1050)
- Moet een rapport data van een heropend gesprek opnieuw bij de bron ophalen en ligt die bron eruit (bijvoorbeeld DUO
  met HTTP 503), dan stopt het ophalen bij de eerste key die faalt. Eerder probeerde de server elke key van het gesprek
  apart, elk met herhalingen en de timeouts van de bron, en zag de gebruiker minutenlang niets. Nu volgt meteen de
  foutmelding, die de bron noemt; staan er meer bronnen in de storing, dan noemt ze alleen de eerste.
- Is een rapport na twee minuten nog niet klaar, dan zegt de voortgang "Dit duurt langer dan normaal. Je kunt blijven
  wachten of het rapport annuleren." in plaats van "Een rapport maken duurt meestal een paar minuten." Een schermlezer
  leest de nieuwe zin voor. Elk einde van het rapport (klaar, fout, geannuleerd of na tien minuten afgebroken) haalt
  hem weg.
