### Het bewijs per antwoord bewaart de kolommen van kaarten niet meer (#1044)
- Sinds de figuren uit het gesprek in het rapport komen (#993) las niets de kolom `kaarten` van `beurtbewijs` nog: een
  kaart uit het gesprek staat als figuurstap in `figuren`. De kolom gaat bij de start weg, op SQLite en PostgreSQL, met
  haar waarden; de rest van elke rij blijft. Ook de export van "Mijn gegevens" en de privacytekst noemen haar niet meer.
- Voor beheer: na deze versie kan een oudere versie niet meer naar `beurtbewijs` schrijven (die verwacht de kolom nog).
  Draai de uitrol dus niet terug tot vóór deze versie.
