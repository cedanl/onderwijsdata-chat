### Vergelijking per hogeschool: geen tabel van één rij onder een conclusie over twaalf (#976)
- De instellingencontrole en `query_data` vielen om op een selectie uit de Studiekeuzedatabase (`KeyError: 'brin'`):
  de app kende alleen de DUO-paren van instellingscode en -naam. De gebruiker zag "een controle kon niet draaien", en
  een selectie op een paar hogescholen gaf "Filter mislukt". De SKDB-kolommen `brin` en `instelling` horen er nu bij.
- Een eigen berekening die op schooljaar filtert (som per instelling over 2021 en 2025) gold niet als bewijs: de
  afhankelijkheidsproef vermenigvuldigde ook de jaarkolom, het filter werd leeg en de proef faalde. Jaarkolommen
  blijven nu staan; wat alleen van het jaar afhangt, telt nog steeds niet.
- Verliest een tabel bij het weglaten van ongedekte getallen meer rijen dan ze houdt, dan houdt de app het antwoord in
  met de meldingen, in plaats van een restant te tonen dat de rest van het antwoord tegenspreekt.
