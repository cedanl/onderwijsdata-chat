### Chat: een koppeling van twee bronnen gaat altijd via koppel_data (#1014)
- `run_analysis` weigert vooraf een script dat tabellen van twee of meer keys samenvoegt met `merge`, `join` of
  `concat`, ook als de tabellen eerst onder een andere naam of na een `groupby` verder gaan. Het model koppelde zo de
  Studiekeuzedatabase en DUO per instelling in één script, en verloor instellingen zonder match (reaudit C02/N07); een
  regel in de prompt hield dat niet tegen.
- De melding noemt de keys, vraagt eerst `relatie` en wijst naar `koppel_data`: moet een bron eerst per instelling
  opgeteld of gemiddeld worden, dan gebeurt dat per bron in een eigen stap, en koppelt `koppel_data` daarna die
  uitkomsten. Een script op één tabel, of met een eigen tabel erbij, draait zoals voorheen.
- Dit is een patroonwacht: wie twee tabellen op een andere manier combineert (`map`, `isin`, een opzoeking), komt
  erlangs.
