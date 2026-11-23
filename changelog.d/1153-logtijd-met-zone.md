### Tijdstempel in het JSON-log met tijdzone (#1153)
- De tijdstempel van elke JSON-logregel is nu het moment van de regel zelf, met zone (`2026-11-20T14:20:36.500852+00:00`).
  Voorheen stond er UTC zonder zone-aanduiding, die een logplatform als lokale tijd las; de regels leken zo een uur
  uit de pas met de tekstregels. `datetime.utcnow()` (verouderd sinds Python 3.12) is uit de code.
