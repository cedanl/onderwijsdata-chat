### /mcp/ met slash is hetzelfde eindpunt als /mcp (#1215)
- Een MCP-client met `/mcp/` als URL kreeg de app-shell (index.html met 200), of zonder frontend een redirect naar
  `/mcp`. Nu antwoordt `/mcp/` net als `/mcp`, zonder redirect: zonder sleutels in `MCP_API_KEYS` een JSON-404, met
  sleutels 401 zonder geldige sleutel en het MCP-antwoord met een geldige. Een POST door een 307/308 breekt veel
  MCP-clients, daarom twee routes en geen redirect.
