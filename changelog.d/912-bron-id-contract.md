### Eén ID-contract bron:id, eerst in schaduwmodus (#912)
- Elke dataset heeft één sleutel `bron:id` (`cbs:85423NED`, `duo:p01hoinges`, `rio:aangeboden-opleidingen`), met één
  normalisatie in onderwijsbronnen. Alle ID-vormen uit opgeslagen recepten en gesprekken blijven geldig; een kale ID die
  bij twee bronnen past, is een fout met de opties in plaats van een stille keuze.
- De vlag `BRON_ID_CONTRACT` (`uit`, `schaduw`, `aan`) bepaalt of de chat de oude of de nieuwe herleiding gebruikt. Op
  test staat hij op `schaduw`: de chat werkt zoals voorheen en logt elk verschil als `BRON_ID_VERSCHIL`.
- Wat het model ziet, blijft gelijk.
