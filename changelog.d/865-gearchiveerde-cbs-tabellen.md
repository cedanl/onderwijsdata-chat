### Een gearchiveerde CBS-tabel zegt dat CBS hem niet meer bijwerkt (#865)
- Ongeveer twee derde van de CBS-tabellen in de chat is gearchiveerd. Zo'n tabel stond in de Bronnen, onder een
  rapportgrafiek en in de kop van een CSV-export precies zo als een lopende tabel. Nu staat er achter de titel
  "gearchiveerd, laatste periode …", met de laatste periode uit de catalogus.
- `get_cbs_data` zet `gearchiveerd` en `laatste_periode` in het resultaat, zodat het model het kan noemen, en een
  zoektreffer draagt hetzelfde etiket, zodat het model een lopende opvolger kan verkiezen. De volgorde in de zoekfunctie
  (lopende tabellen eerst) blijft.
