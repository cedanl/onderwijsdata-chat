### `from onderwijsbronnen.cbs import data` blijft de functie na een catalogusaanroep (#1104)
- De catalogusbestanden van CBS stonden in het subpakket `onderwijsbronnen.cbs.data`, dezelfde naam als de functie
  `data`. Zodra iets in het proces de catalogus laadde (`catalog()`, `catalog_manifest()`, `normaliseer_bron_id`,
  `onderwijsbronnen.catalogus()`), overschreef het geïmporteerde subpakket het attribuut `cbs.data`: een CBS-snippet
  na de README-controleregel gaf `TypeError: 'module' object is not callable`.
- De map heet nu `onderwijsbronnen/cbs/catalogusdata/`. Publieke namen veranderen niet; wie de bestanden rechtstreeks
  via het pad las, vindt ze onder de nieuwe mapnaam. Een test per aanroep en een mapnaamcontrole leggen het vast.
