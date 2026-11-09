### Na heropenen tellen alleen eigen antwoorden als bewijs, en feedback zegt of het antwoord van de server kwam (#876)
- Een getal uit een eerder antwoord telt als gedekt. Na heropenen of herverbinden komt dat antwoord uit de browser;
  het telt nu alleen als de server het zelf schreef, dus als de hash van de tekst een rij in `beurtbewijs` heeft
  (ADR-009). Een antwoord zonder rij telt niet, ook niet als eerder gesprek voor de weigering van een getal zonder
  data: een gesprek van vóór het bewijs per antwoord (#875), een herstart vóór het opslaan, een gestopt antwoord of een
  tekst die de browser veranderde. Zo'n vervolgvraag krijgt daardoor vaker een herschrijving of een weggelaten getal. Een levend
  gesprek verandert niet.
- De meldingen van de controles onder een antwoord staan nu ook in zijn rij (nieuwe kolom `controle`, op SQLite en
  PostgreSQL vanzelf toegevoegd bij de start; oudere rijen krijgen een lege lijst). De feedbacktrace leest de controle
  daar, niet uit het gesprek dat de browser opsloeg, en krijgt `tekst_hash` en `server_beurt`. Feedback op een antwoord
  zonder rij wordt aangenomen met `server_beurt: false`. Het overzicht voor het team (`scripts/antwoordfeedback.py`)
  toont het.
- De export van "Mijn gegevens" en de privacytekst noemen de meldingen van de controles bij het bewijs per antwoord.
