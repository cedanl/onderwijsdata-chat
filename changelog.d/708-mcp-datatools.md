### Cijfers via MCP: aantallen per jaar en instellingen vergelijken (#708)
- Twee sessieloze datatools in de MCP-server, via stdio en `/mcp`: `aantallen_per_jaar` geeft het aantal studenten,
  eerstejaars of inschrijvingen van één mbo-, hbo- of wo-instelling, of van één hbo/wo-opleiding daar, per studiejaar
  met het verloop; `vergelijk_instellingen` zet die reeks voor twee tot acht instellingen naast elkaar, met de
  volgorde in het laatste gedeelde jaar. Bron: DUO.
- Eén aanroep haalt op en rekent met dezelfde code als de chat: het recept van `get_maat`, per opleiding op het
  niveaubestand van de maat, en `compute_kpi` voor het verloop. Geen `data_key` naar buiten, geen toestand per
  gebruiker. Elk resultaat heeft `bewijs` (dataset, recept, teldefinitie, versie van het DUO-bestand) en `vervolg` met
  dezelfde vraag als link naar de volledige app.
- Fail-closed zoals de chat: alleen instellingen uit het register (mbo, hbo, wo); een vo-school, een onbekende naam of
  mbo naast hbo/wo is een fout met de reden. De sleutel, limieten, tijdslimiet en het afkappen van `/mcp` gelden ook
  hier. Landelijke cijfers, mbo per opleiding, rapporten, exports en arbeidsmarkt blijven in de volledige app.
- De chat zelf verandert niet.
