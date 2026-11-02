### Een percentage in een rapport komt uit de data of uit compute_kpi (#872)
- De rapportrun kon een groeicijfer of verschil alleen uit de `query_data`-uitvoer overnemen; stond het daar niet,
  dan rekende het model het zelf uit, en de rapportcontrole liet een percentage als "+8 %" ongetoetst door. Nu heeft
  de rapportrun `compute_kpi`, en toetst de controle elk percentage dat het model schreef met dezelfde regel als in
  de chat: als waarde of als fractie in de data, afgerond zoals in de tekst. Een ongedekt percentage krijgt één
  herkansing en houdt daarna het rapport tegen, net als een ongedekt groot getal.
- De definities uit de bron vallen buiten die toets: daar rekent het model niets.
