### Mijn gegevens: het tokengebruik gaat mee in de export en het verwijderen, en zonder login geen export (#1074, #1118)
- "Verwijder al mijn gegevens" wiste het tokengebruik per dag niet (`tokengebruik`, #678): het staat onder een
  pseudoniem van de accountnaam (#1112), niet onder `username`, en viel zo buiten het verwijderen en de export. Nu
  verwijdert het verwijderen die rijen in dezelfde transactie, met een aantal `tokengebruik` in `verwijderd`; de dag-
  en maandteller van het account beginnen daarna opnieuw.
- De export heeft een lijst `tokengebruik` met per dag `dag` en `eenheden`, op volgorde van de dag, zonder het
  pseudoniem. Alleen een sleutel erbij: `schema_version` blijft 1.
- Zonder login (iedereen is de gedeelde `gast`) antwoordt `GET /api/mijn-gegevens/export` nu 404, zoals het
  verwijderen al deed: de export van `gast` bevatte het werk van alle bezoekers. De instellingen tonen de knop
  "Exporteer al mijn gegevens" dan niet meer. Een demo met `ALLOW_ANONYMOUS=true` heeft zo geen export.
- De privacytekst in de app en `docs/privacy.md` noemen het tokengebruik bij wat de export bevat en wat het
  verwijderen wist.
