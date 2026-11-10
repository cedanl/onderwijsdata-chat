### De dagelijkse bron-ping bewaakt ook de Studiekeuzedatabase, zonder sleutel (#878)
- Nieuwe ping `skdb-openapi` in `bron:ping`: leest de openbare OpenAPI-spec van LCSK (`api.skdb.nl/v1/openapi.json`)
  en is rood zodra `/export/json` geen ZIP meer levert of een van de negen tabellen van `get_studiekeuze` niet meer in
  de API staat. De melding noemt het pad of de tabel die ontbreekt.
- De tabellen komen uit de code (de tabellen die de zes weergaven lezen), niet uit een vaste lijst: een weergave die
  een tabel gaat lezen, valt vanzelf onder de ping.
- De sleutel van LCSK is niet nodig en staat niet in CI (afspraak #878): de ping stuurt hem ook niet mee als hij in de
  omgeving staat. De inhoud van de export (velden, aantallen) ziet de ping daardoor niet.
