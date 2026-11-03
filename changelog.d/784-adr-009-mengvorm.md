### Besluit over de bron van waarheid voor gesprekken vastgelegd (#784)
- ADR-009 in `docs/architecture-decisions.md`: de browser blijft het gesprek bewaren, en de server bewaart straks per
  beurt de herkomst van de data, het rekenbewijs, de kaarten en een hash van het gecontroleerde antwoord. Een rapport op
  een heropend gesprek krijgt dan dezelfde context als in het lopende gesprek. Nog niet gebouwd (#875, #876);
  de app werkt nog zoals voor dit besluit.
