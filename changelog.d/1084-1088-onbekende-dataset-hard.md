### Een verzonnen dataset-ID houdt het antwoord in; een ID dat de vraag of een tool noemde niet (#1084, #1088)
- Noemde het model een dataset-ID dat niet in de catalogus staat als bron ("Volgens CBS-tabel 85999NED …"), dan bleef
  dat na een mislukte herkansing in de lopende tekst staan, met alleen een "Let op". De controle is nu hard: blijft zo'n
  ID staan, dan houdt de app het antwoord in, net als bij een verzonnen getal.
- Een ID dat de gebruiker zelf noemde (de vraag of een eerder bericht) of dat een toolresultaat in deze beurt noemde,
  telt niet als verzonnen. Zegt het antwoord terecht dat "CBS-tabel 99999NED niet in de catalogus staat", dan krijgt het
  geen "Let op" en geen herkansing meer. Dezelfde regel geldt voor de controle op een rapport (de bronnen van de run).
