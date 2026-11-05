### MCP-SDK in het image, litellm naar 1.108 (#938)
- `mcp` is een gewone dependency en geen extra meer: het runtime-image heeft hem nu, als voorwaarde voor `/mcp` in de
  app (#706). `uv sync` installeert hem; `uv sync --extra mcp` bestaat niet meer. De Docker-build faalt als
  `import mcp.types` niet lukt.
- De cap `litellm<1.106` is weg; litellm gaat van 1.105.5 naar 1.108.0 (de update van Renovate-MR !801). De cap
  bestond omdat litellm sinds 1.106 `mcp` importeert bij elke aanroep met tools, en `mcp` niet in het image zat.
  Gemeten met de tools van de chat: de eerste aanroep met tools per proces duurt eenmalig ±0,65 s langer en het
  geheugen ligt daarna ±10 MB hoger; volgende aanroepen zijn even snel. Geen threads, bestanden, netwerk of
  omgevingsvariabelen erbij.
- `tests/test_litellm_mcp.py` vervangt `tests/test_litellm_zonder_mcp.py`: `mcp` blijft een gewone dependency, een
  aanroep met tools werkt in een vers proces, en de tools van de chat gaan niet via de MCP-gateway van litellm.
- filelock blijft 3.32.7: ook litellm 1.108.0 eist `filelock<4.0`, dus de tien filelock-CVE's van #767 blijven open.
  `mcp` en zijn afhankelijkheden brengen geen nieuwe CVE's mee.
