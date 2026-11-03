### Een heropend gesprek geeft hetzelfde rapport als het levende gesprek (#875)
- Het rapport op een heropend of herverbonden gesprek kent weer waar de data van elk antwoord vandaan kwam, de
  berekeningen (KPI en eigen analyses) en de kaarten die in het gesprek stonden. Voorheen stond bij zo'n gesprek in de
  rapportprompt "onbekend (niet vastgelegd in dit gesprek)" en ontbraken de berekeningen en kaarten.
- De server bewaart daarvoor per afgerond antwoord een rij in de nieuwe tabel `beurtbewijs` (ADR-009): de herkomst van de
  data, het rekenbewijs en de kaartkolommen, onder een hash van de antwoordtekst. Niet de vraag, het antwoord of de
  rijen van een kaart. De rij wordt geschreven zodra de browser het gesprek opslaat; bij heropenen of herverbinden
  vóór die opslag staat ze nog in het geheugen van de server.
- Een antwoord waarvan de tekst onderweg veranderde, een gestopte beurt en een opslag die met 409 wordt geweigerd
  krijgen geen rij. Gesprekken van vóór deze wijziging heropenen zoals voorheen.
- De rijen gaan weg met het gesprek (verwijderen en opschonen; een rij zonder gesprek na 90 dagen) en met "Verwijder al
  mijn gegevens", en staan in de export (`beurtbewijs`). De privacytekst en `docs/privacy.md` noemen de nieuwe soort.
- Een rij met een kaart en een berekening is ongeveer 1 kB. De bovengrens volgt uit het rekenbewijs (hoogstens de
  laatste 30 uitkomsten, elk hoogstens 12.000 tekens).
