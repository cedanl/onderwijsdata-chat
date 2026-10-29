### Een verwijdering die bij het sluiten van de tab mislukt, gaat bij het volgende bezoek opnieuw (#801)
- Sloot je binnen de bedenktijd de tab en mislukte de DELETE die meeging, dan stond het gesprek bij het volgende bezoek
  zonder uitleg weer in de lijst. Nu staat het id van het gesprek (geen titel of inhoud) vanaf het verwijderen in een
  wachtrij in de browser, tot de server de verwijdering bevestigt (een 404 telt mee). Bij het laden van de chat gaan
  die verwijderingen eerst opnieuw en tonen de lijst ze niet; lukt het weer niet, dan komt het gesprek terug met de
  melding en "Opnieuw proberen" (#778).
- De wachtrij hoort bij het account (`SESSION_DATA_KEYS`): uitloggen stuurt haar eerst nog met het eigen token, en
  uitloggen, een nieuwe login en het einde van de sessie wissen haar. Ongedaan maken of een nieuwe vraag in het gesprek
  haalt het id eruit.
