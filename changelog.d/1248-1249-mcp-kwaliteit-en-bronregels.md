### Een MCP-client krijgt de datakwaliteit en de gebruiksregels mee (#1248, #1249)
- Elk resultaat van `aantallen_per_jaar` en `vergelijk_instellingen` heeft in `bewijs` een blok `kwaliteit`: hoeveel
  onderdrukte cellen er achter de reeks zitten en of de aantallen daardoor een ondergrens zijn (met de zin uit de
  domeinregel), welke gevraagde schooljaren ontbreken, of de bron afgekapt was en welke codes van de instelling niet
  gevonden zijn. Bij een vergelijking per instelling. De catalogustools hebben `kwaliteit: null`. Alleen een nieuwe
  sleutel: de bestaande blijven zoals ze waren.
- Een instelling zonder één rij in de selectie (niet in de gevraagde jaren of vorm) is geen ondergrens: de
  onderdrukte cellen van andere instellingen tellen niet mee, en al haar codes staan bij `niet_gevonden`.
- `get_maat` geeft een mbo-instelling zonder rij in de selectie een lege reeks; eerder kreeg ze de rijen van het hele
  bestand, van elke andere instelling.
- De MCP-server biedt de prompt `bronregels`, met dezelfde tekst als resource `onderwijsdata://bronregels`: de ondergrens
  noemen, `bewijs.versie` noemen, niet gevonden is niet "bestaat niet", niet zelf rekenen, en de domeinregels van DUO
  uit `data/domeinregels.toml`. De instructies van de server verwijzen ernaar. Een client kan de regels negeren: het is
  een werkinstructie, geen controle. Over `/mcp` geldt dezelfde API-sleutel als voor de tools.
