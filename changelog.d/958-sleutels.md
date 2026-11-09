### Het model ziet vóór het laden via welke sleutel een dataset koppelt (#958)
- `search_catalog` en `dataset_details` noemen per dataset `koppelbaar_via`: de sleutels waarop hij met een andere bron
  koppelt (brin, croho, crebo, gemeente, provincie, schooljaar, …). Een zoekhit noemt ze kort, het detailrecord per
  sleutel met de kolom, of waarom een dataset geen sleutel heeft. Bij een vraag over twee bronnen (NSE uit de
  Studiekeuzedatabase naast instroom uit DUO) plant het model de koppeling zo vóór het laadt, in plaats van eerst te
  laden en dan te ontdekken of het past.
- Eén lijst: de sleutels staan in het pakket (`onderwijsbronnen.sleutels`), met de kolomnamen per bron en een pure
  vertaling van de waarden. `relatie`, het datasetcontract (`join_sleutels`) en het schema van de Studiekeuzedatabase
  gebruiken dezelfde lijst; de connectoren in de chat en de voorvoegsels in het contract zijn weg.
- `relatie` noemt de sleutels voortaan bij hun canonieke naam: `brin` in plaats van `instellingscode`, `croho` of `crebo`
  in plaats van `erkende_opleiding`. Nieuw herkend: `VESTIGINGSCODE` (vestiging), het bestuursnummer, de gemeente en
  provincie van een mbo-instelling en de woonprovincie, de SOI-rubriek en het ROA-opleidingstype. `DIPLOMAJAAR` telt niet
  meer als schooljaar (CH-41), en een opleidingscode met voorloopnul (04181) is dezelfde als 4181.
- Elk catalogusrecord heeft `_sleutels` of een reden waarom niet. Het veld scoort niet mee in `search_catalog`: de
  zoekhits zijn gelijk gebleven; de retrieval-baseline is alleen op de nieuwe catalogusdigest opnieuw vastgelegd.
