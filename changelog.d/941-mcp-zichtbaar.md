### Zichtbaar of MCP aan staat (#941, audit L-07)
- `/version` heeft een veld `mcp`: `true` als `/mcp` aan staat (`MCP_API_KEYS` gezet), anders `false`. Zo is na een
  deploy zonder sleutel te zien of de MCP-server er is; over de sleutels zelf zegt het niets.
- Staat `APP_URL` gezet (een omgeving die `/mcp` hoort aan te bieden, zoals test) maar ontbreekt `MCP_API_KEYS`, dan
  logt de start een WARNING in plaats van een INFO-regel.
