### Een open chatverbinding volgt het intrekken en verlopen van het token (#786)
- De server toetste het token alleen bij het verbinden; de hartslag hield de verbinding daarna onbeperkt open. Een
  tabblad dat open bleef, kon na uitloggen elders of na het verlopen van de sessie nog vragen, rapporten en dashboards
  laten draaien. Nu toetst de server het token vóór elke vraag, verduidelijking, dashboard, rapport en verversen
  opnieuw en sluit hij bij een ongeldig token de verbinding (code 4001), zonder run. Is het token intussen ververst,
  dan verbindt de app opnieuw in plaats van uit te loggen.
- "Verwijder al mijn gegevens" trekt nu alle tokens van het account in, ook die van een ander apparaat. Een open sessie
  daar kan zo geen gesprek meer terugzetten. De server bewaart daarvoor tot de laatste sessie verloopt alleen een hash
  van de accountnaam met het moment van verwijderen (`revoked_users`).
