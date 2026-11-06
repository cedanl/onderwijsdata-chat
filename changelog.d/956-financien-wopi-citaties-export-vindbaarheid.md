### Citaties, telling en export voor de financiën en WOPI; suggesties en vindbaarheid per omgeving (#956)
- Een antwoord met de financiën van een bestuur (`get_bestuursfinancien`) of met WOPI-personeel (`get_wo_personeel`)
  heeft nu citaties: elk kengetal van bestuur en sector, het verschil, de rijksbijdragen, de signaleringswaarde (met de
  Inspectie als bron) en elk fte-, personen- en aandeelcijfer, met eenheid en selectie (bestuur of instelling,
  verslagjaar of peildatum, variant, met of zonder GEZO). Ook een getal met een decimale komma (solvabiliteit 0,69,
  6.184,36 fte) krijgt een citatie als het op een waarde van deze tools past.
- De tabel achter het resultaat staat in de store, met bron, dataset (`duo:financien`, `unl:wopi`), editie of
  peildatum en laadaanroep: de CSV-export met inhoudshash werkt, de data komt na een herstart uit haar recept terug, en
  een volgende stap (selectie, grafiek) heeft een snippet die bij de bron begint. Een export noemt nu bij elke
  momentopname of editie ook het peilmoment.
- Telling: bij de financiën over hoeveel eenheden het sectorcijfer gaat en een fusie in de reeks, bij WOPI wat fte en
  personen tellen en de GEZO-variant.
- Startscherm: vragen over de financiën (mbo, hbo, wo) en over WOPI (alleen wo), alleen waar die bron antwoord geeft.
- search_catalog vindt WOPI als `via_tool` waar de vlag aan staat; de financiën staan, als de licentie niet als
  bevestigd geldt, als `alleen_catalogus`. De tellingen op de startpagina en in het venster Databronnen tellen bronnen met een eigen tool
  (UWV, ROA, de financiën, WOPI) mee waar die antwoord geven.
