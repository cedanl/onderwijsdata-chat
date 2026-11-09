### Limieten op /mcp, los van de chat (#940)
- Rate limit per sleutel (`MCP_RATE_LIMIT`, 60) en per IP (`MCP_RATE_LIMIT_IP`, 120, ook voor een foute sleutel) per
  `MCP_RATE_WINDOW_S` (60 s): daarboven HTTP 429 met `Retry-After`. Achter de ingress is het IP dat van de ingress zolang
  `FORWARDED_ALLOW_IPS` niet gezet is; dan werkt de grens per IP als totaalgrens voor `/mcp`.
- Hooguit `MCP_MAX_GELIJKTIJDIG` (4) verzoeken tegelijk; een volgend krijgt na `MCP_WACHT_S` (1 s) een 503 met
  `Retry-After`, geen lange wachtrij. Toolaanroepen draaien in eigen threads, los van die van de chat.
- Een toolaanroep stopt na `MCP_TOOL_TIMEOUT_S` (30 s) met een MCP-fout; een resultaat boven `TOOL_RESULT_MAX_CHARS`
  wordt afgekapt tot een geldige envelope met `melding`, `begin`, `bewijs` en `vervolg`.
- Voorzichtige standaarden; de definitieve waarden volgen uit de belastingsmeting (#942).
