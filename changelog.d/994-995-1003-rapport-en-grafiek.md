### Een rapport staat op zichzelf (#994)
- De rapportcontrole weigert tekst die naar "het gesprek" of "de chat" verwijst als plek waar iets te zien is, en tekst die
  een grafieksoort noemt (sankey-diagram, kaart, taartdiagram, spreidingsdiagram, lijngrafiek, staafdiagram, heatmap,
  treemap) die geen figuur van het rapport heeft. Het model krijgt eerst een herkansing; blijft de verwijzing, dan wordt
  het rapport geweigerd, zoals bij de andere harde controles. De soort van een figuur leest de code uit de figuur zelf.
