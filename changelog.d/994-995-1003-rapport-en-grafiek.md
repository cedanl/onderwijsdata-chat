### Een rapport staat op zichzelf (#994)
- De rapportcontrole weigert tekst die naar "het gesprek" of "de chat" verwijst als plek waar iets te zien is, en tekst die
  een grafieksoort noemt (sankey-diagram, kaart, taartdiagram, spreidingsdiagram, lijngrafiek, staafdiagram, heatmap,
  treemap) die geen figuur van het rapport heeft. Het model krijgt eerst een herkansing; blijft de verwijzing, dan wordt
  het rapport geweigerd, zoals bij de andere harde controles. De soort van een figuur leest de code uit de figuur zelf.

### Sankey-diagram voor doorstroomvragen (#995)
- `create_plot` kent `chart_type: "sankey"`, met `source` (herkomst), `target` (bestemming), `value` (aantal) en
  optioneel `color`. Chat en rapport tekenen een doorstroom zo uit code, met de kleuren, letters, bronregel, CSV en
  afrondingsnoot van de andere grafieken, in plaats van met Plotly-code van het model. Knopen staan op grootte; een stroom
  met 0 of leeg valt weg en het toolbericht zegt hoeveel. Boven 40 knopen komt er geen figuur maar een vraag om te
  filteren of te groeperen. De hover toont het aantal en het aandeel van de herkomst.
- `x` en `y` zijn niet meer verplicht in het schema; een ander type zonder `x` of `y` krijgt een duidelijke melding. Het
  recept (snippet) tekent de sankey ook, en "maak een sankey" of "stroomdiagram" wordt op een sankey getoetst.
