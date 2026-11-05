### Het ID-contract bron:id is het enige pad; de oude pakketnamen zijn weg (#914)
- De vlag `BRON_ID_CONTRACT` en de oude herleiding van dataset-ID's zijn weg: de chat volgt altijd het ID-contract
  `bron:id`, zoals sinds 2.7.0 al op test en playground. Elke oude ID-vorm in opgeslagen recepten en gesprekken
  blijft werken; de logregel `BRON_ID_VERSCHIL` bestaat niet meer.
- Het pakket `onderwijsbronnen` (0.9.0) kent de overgangsnamen `riodata` en `onderwijsdata` niet meer. Een opgeslagen
  snippet met `from riodata import duo` of `from onderwijsdata import data` draait tegen de installatie die zijn kop
  noemt (de oude pakketrepo's of een oudere commit van deze repo); in nieuwe code wordt dat
  `from onderwijsbronnen import duo` en `from onderwijsbronnen.cbs import data`.
- Beheer: bij de eerste promotie van een release met deze wijziging gaat `BRON_ID_CONTRACT` ook uit
  `manifests/playground` (`docs/promoten.md`).
