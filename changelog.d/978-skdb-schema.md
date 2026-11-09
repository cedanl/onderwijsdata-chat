### Het schema van de Studiekeuzedatabase is te vinden en op te vragen (#978)
- Op test en playground vindt `search_catalog` de Studiekeuzedatabase op een tabelnaam ("tracks", "studieadvies",
  "opendagen") en op "skdb". Een hit noemt de geraakte tabel en wat de chat ermee kan, en de weg naar het schema.
- `dataset_details("skdb:studiekeuzedatabase")` geeft naast de verwijzing naar `get_studiekeuze` het schema uit de export
  van vandaag: de editie (versie, exportdatum, NSE- en 1cijferHO-jaar), wat een leeg veld betekent, en per tabel de
  omschrijving, het aantal kolommen en wat de chat ermee kan. `dataset_details("skdb:studiekeuzedatabase/<tabel>")` geeft
  het schema van één tabel: kolommen met type, korrel, sleutels naar andere bronnen, relaties en jaarkolommen. Een vraag
  naar het schema hoeft dus niet meer "dat kan ik niet raadplegen" te krijgen.
- Per tabel staat wat er kan: een weergave van `get_studiekeuze`, alleen in het pakket leesbaar (`skdb.load`), of bewust
  niet in de chat omdat een andere bron leidend is (wettelijk collegegeld, loon uit CBS-microdata). Kolommen die de chat
  volgens de afspraken niet toont (aantallen studenten en eerstejaars, accreditatie, collegegeld) dragen de leidende bron.
  Zo is te zien of "niet beschikbaar" over de bron gaat of over de tool. De zes weergaven blijven zoals ze waren.
- Alleen de tabelnamen staan in de code; de omschrijvingen, kolommen en types zijn het woordenboek van LCSK en komen
  alleen uit de export, niet uit de repo of de catalogussite. Elk schema-antwoord draagt de bronregel van LCSK.
- Pakket `onderwijsbronnen`: nieuw `skdb.schema(export)`; het catalogusrecord heeft de tabelnamen en de tag `skdb`.
- `relatie` herkent de ruwe SKDB-kolom `opleidingCode` als CROHO-code.
