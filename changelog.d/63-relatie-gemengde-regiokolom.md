### `relatie` herkent de gemeente in een gemengde CBS-regiokolom (#63)
- Een CBS-regiotabel mengt Nederland, landsdelen, provincies, COROP-gebieden en gemeenten in één kolom. `relatie` las die
  alleen als sleutel als álle waarden een gemeentecode waren, en meldde dus bijna nooit een koppeling op gemeente tussen
  DUO en CBS. Nu telt de soort met de meeste codes, vanaf de helft van de waarden; de overige regio's tellen niet mee in
  `uniek`, `dekking` en `overlap`. Gemeten op CBS 85701NED tegen DUO `p01hoinges`: 446 gemeenten, 43 gedeeld.
