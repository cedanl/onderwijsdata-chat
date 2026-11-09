### De catalogustools van de MCP-server ook over HTTP, op /mcp in de app (#706)
- `search_catalog`, `dataset_details` en `dataset_counts` zijn nu ook bereikbaar als streamable-http-endpoint op `/mcp`,
  in dezelfde app en pod als de chat, zodat SURF AI Chat (EduGenAI) ze als extensie kan aanroepen. Stateless, met
  JSON-antwoorden: geen sessie per client. Dezelfde definities, instructies en uitvoering als de stdio-server
  (`python mcp_server.py`, ongewijzigd), dus dezelfde envelope met `bewijs` en `vervolg`, scopegrens en statussen.
- Zonder sleutels in `MCP_API_KEYS` bestaat `/mcp` niet (404, ook voor GET); `/health`, `/version` en de chat werken
  zoals voorheen. Nog op geen omgeving: eerst test (#941).
