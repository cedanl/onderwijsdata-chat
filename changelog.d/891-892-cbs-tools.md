### CBS-tools: `sector` naast `selectie` en de dimensienaam uit dataset_details (#891, #892)
- `get_cbs_data` neemt een `sector` op het hoogste niveau over in de selectie, zoals het model hem soms meegeeft. Staat
  hij ook in `selectie`, dan wint die. Eerder gaf dat een TypeError, een kale foutmelding en na drie toolfouten een
  geblokkeerde tool, zonder getal.
- Een argument dat een tool niet kent, geeft nu een melding met de naam van het argument, waar het hoort (bijvoorbeeld
  `periode` hoort binnen `selectie`) en welke argumenten wel mogen, in plaats van "faalde (TypeError)". De waarde komt
  niet in de melding.
- `get_cbs_dimension` kent de dimensienaam zoals `dataset_details` hem toont ("Geboorteland (ouders)") en vertaalt hem
  naar de API-naam (`GeboortelandOuders`). Dat scheelt een toolstap en een model-beurt per vraag over zo'n tabel.
