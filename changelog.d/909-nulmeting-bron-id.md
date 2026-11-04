### Nulmeting vóór de overgang naar onderwijsbronnen: opgeslagen ID-vormen als fixture, eval met de bron per vraag (#909)
- Nieuwe fixture `tests/fixtures/bron_id_vormen.json`: welke tool-namen, dataset-ID's, DUO-bestanden, store-keys en
  snippetregels in de opgeslagen recepten, gesprekken en rapporten van test en playground staan, met aantallen en alleen
  publieke ID's. `tests/test_bron_id_vormen.py` haalt elke vorm door de herleiding van nu (`bron_id`, `cbs_bron_id`,
  de scopegrens, de DUO-bestandskeuze, `bron_van` en het herladen van recepten op de bevroren bronnen van de gouden
  tests). Dat is het referentiepunt voor #910 en #912.
- `eval:bronwaarheid` legt per vraag de tools en de bron vast (`tools` en `bronnen` per run in
  `eval_results/runs.jsonl`): tool, `dataset_id`, `resource` of `maat` per aanroep. Zo is een latere run per vraag
  tegen de nulmeting te leggen, niet alleen op geslaagd of niet.
- De eval-runner wacht op de berichtlimiet (30 verzoeken per 10 minuten per account) en de inloglimiet (5 per minuut)
  van de app, in plaats van te falen. De run van 04-11 op test (pipeline 792771) faalde vanaf de tiende minuut op elke
  vraag, eerst met "Te veel verzoeken in korte tijd" en daarna, na een mislukte test, met een lege token.
