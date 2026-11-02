### Een lijn met aantallen begint op 0; een afgekapte as staat erbij (#871)
- Een lijngrafiek begon standaard bij het kleinste getal, zodat het model per grafiek bepaalde hoe dramatisch een
  trend oogde. Nu volgt de asbasis in code de eenheid van de getekende kolom: een telling (CBS 'aantal', 'absoluut',
  'x 1 000') of een kolom zonder eenheid begint op 0; een percentage, index of bedrag niet, en dan staat "as begint
  niet bij 0" onder de astitel. `y_vanaf_nul` blijft een keuze voor de gebruiker, in beide richtingen, en de
  Python-snippet tekent dezelfde as.
- Dezelfde regel in de vaste dashboards: de sector- en leerwegtrends beginnen op 0, de rendementslijn zegt het als
  haar as niet bij 0 begint.
