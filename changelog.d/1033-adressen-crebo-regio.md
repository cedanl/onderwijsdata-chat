### Catalogus en sleutels volgen de data: adressen, crebo en arbeidsmarktregio (#1033, #1034, #1035)
- `get_duo_data("adressen_ho")` en `get_duo_data("adressen_mbo")` zonder bestandskeuze laden nu de adressen van de
  instellingen (bestand 1, met `INSTELLINGSCODE`), niet die van de besturen (bestand 0, zonder BRIN). Wie bestand 0
  noemt, krijgt nog steeds de besturen.
- `BEROEPSOPLEIDING CODE` van DUO (bijvoorbeeld `bc365`) geldt niet meer als crebo-sleutel: het is DUO's eigen code
  van de beroepsopleiding, geen crebo-code. `relatie` en `koppelbaar_via` boden daar een koppeling op crebo aan die
  nooit paste. De kolommen met echte crebo-codes (`ERKENDE OPLEIDING CODE`, `CREBO`, `ERKENDEOPLEIDINGSCODE`) blijven
  crebo.
- CBS 85353NED (mbo-studenten) en 85356NED (mbo-gediplomeerden) noemen in de catalogus nu wat `Regio` bevat: vooral
  arbeidsmarktregio's, naast provincies, landsdelen en enkele gemeenten. `koppelbaar_via` noemt de arbeidsmarktregio,
  net als `relatie` op de geladen kolom; de tag `corop` is weg bij 85353NED.
