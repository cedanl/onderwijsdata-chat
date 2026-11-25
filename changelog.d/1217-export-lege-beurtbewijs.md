### Mijn gegevens: een lege rij bewijs per antwoord zegt in de export waarom ze leeg is (#1217)
- Een antwoord zonder toolstap gaf in `GET /api/mijn-gegevens/export` een `beurtbewijs`-rij met lege `lineage`,
  `rekenbewijs`, `bronnen` en `figuren`, wat op ontbrekende data leek. Zo'n rij heeft nu de sleutel `reden_leeg` met
  "geen toolstap in deze beurt"; een rij met inhoud krijgt die sleutel niet. De rijen blijven allemaal in de export, en
  `schema_version` blijft 1: er komt alleen een sleutel bij.
