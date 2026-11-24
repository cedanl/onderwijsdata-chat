### Catalogus: een zoekterm over po of vo is altijd out_of_scope, ook met treffers (#1093)
- `search_catalog` toetste de po/vo-scope alleen als de zoektocht niets vond. Een zoekterm als "basisonderwijs
  leerlingen", "leerlingen voortgezet onderwijs", "havo vwo eindexamen" of "vo examens" gaf daardoor mbo- en
  ho-tabellen zonder scope-melding, in de chat en aan een MCP-client. Nu geeft elke zoekterm die po, so of vo noemt
  zonder mbo, ho of doorstroom erbij `out_of_scope`, vóór er gezocht wordt.
- "doorstroom havo hbo" en "doorstroom vmbo mbo" blijven een gewone zoekvraag met de gelabelde vo-contexttabellen. Zoekt
  het model in een beurt op "havo" terwijl de vraag van de gebruiker over het hbo gaat, dan blijft het ook een zoekvraag.
