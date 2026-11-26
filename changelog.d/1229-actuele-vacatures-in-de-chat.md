### Arbeidsmarkt: de chat geeft de actuele vacatures van CBS, UWV is een archief (#1229, #1226, #1227)
- Nieuwe tool `get_vacatures`: de openstaande vacatures per provincie en bedrijfstak uit CBS 83599NED, het laatste
  kwartaal en het gemiddelde van de laatste vier kwartalen, elk met de periode en "voorlopig" waar CBS dat zegt. Een
  lege cel is "geen gegevens", geen 0. Vraag je naar een gemeente, woonplaats of arbeidsmarktregio, dan geeft de chat de
  provincie waarin die ligt en zegt dat de actuele cijfers tot provincie gaan.
- Nieuwe tool `get_ontstane_vacatures`: de ontstane vacatures per jaar (2018-2025) en beroep (BRC 2014, beroepsklasse
  of -segment), landelijk, uit CBS 85081NED. De eenheid komt uit de metadata van de tabel.
- Beide resultaten zijn een dataset: bronnenlijst, citaties, "Bekijk code", herladen na een herstart en de CSV-export
  werken zoals bij andere bronnen. `search_catalog` en `dataset_details` wijzen bij 83599NED en 85081NED naar hun tool.
- `get_uwv_vacatures` is een archief: elk antwoord begint met de peildatum 16-05-2023 en de melding dat UWV deze reeks
  niet meer maakt. De systeemprompt stuurt het model eerst naar de CBS-vacatures; UWV alleen bij een vraag naar mei 2023.
- 85081NED staat in de CBS-catalogus met titel, licentie, frequentie en de status per jaar.
