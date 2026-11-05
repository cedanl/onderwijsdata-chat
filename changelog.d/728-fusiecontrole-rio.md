### Fusies van instellingen: "opgegaan in" bij een oude naam en een vaste regel bij een reeks (#728)
- Een oude naam of BRIN gaf "niet gevonden": "Friesland College" of `25LG` zegt nu "Regionaal Opleidingen Centrum
  Friesland College (25LG) is per 1 augustus 2023 opgegaan in Firda (08PG) (volledige overgang)". Helicon Opleidingen
  meldt de gedeeltelijke overgang naar Yuverta. "Regio College" gaf zonder melding het overzicht van Talland; nu staat
  erbij dat het roc (25RA) per 1 augustus 2024 in Talland College opging. De zin komt uit code en staat ook onder het
  antwoord. `get_rio_instelling` neemt ook een BRIN-code aan.
- DUO rekent een meerjarige reeks per instelling om naar de huidige code: Firda telt in 2021 en 2022 ook Friesland
  College mee. Valt een fusie binnen de reeks, dan krijgt het Telling-blok de regel "DUO telt de jaren vóór de fusie
  (datum) bij de huidige instelling (voorgangers: …)". In de reeksen 2021–2025 geldt dat voor Vonk, KW1C, Firda,
  Drenthe College Terra, Talland en Landstede. De voorgangers komen uit RIO met een dagcache; een storing geeft geen
  regel en breekt het antwoord niet. De bron-ping `rio-fusies` bewaakt de zes.
- Een peildatum in het verleden las de RIO-relaties van vandaag: "Friesland College" op 2022-10-01 vond een bestuur
  "zonder mbo-instelling". `get_rio_instelling` leest relaties en erkenningen nu op de peildatum.
- `riodata` heeft `opvolgers(brin, peildatum)` en `voorgangers(brin, sinds)` langs `OVERGANG_VOLLEDIG` en
  `OVERGANG_GEDEELTELIJK`. Het DUO-register "Basisgegevens instellingen" komt er niet bij: RIO heeft bij mbo, hbo en wo
  dezelfde fusiehistorie.
  Ze werken ook met een bestuursnummer: besturen fuseren langs dezelfde relaties (Stichting Regio College, 40864, in
  Stichting Talland College, 40877, per 1 januari 2024).
