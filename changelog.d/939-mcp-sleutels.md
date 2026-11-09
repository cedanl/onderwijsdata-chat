### /mcp alleen met een API-sleutel (#939)
- Elk verzoek op `/mcp` draagt `Authorization: Bearer <sleutel>` met een sleutel uit `MCP_API_KEYS`; anders 401. Meer
  sleutels tegelijk (kommagescheiden), zodat een sleutel kan roteren zonder onderbreking en elke consument een eigen
  sleutel heeft. Constant-time vergeleken; de sleutel komt nooit in een log of foutmelding, het log noemt per aanroep
  een sleutel-ID (`sleutel_len=… sleutel_hash=…`).
- `manifests/test/values.yaml` leest `MCP_API_KEYS` optioneel uit de secret, met een nieuw sjabloon
  `manifests/test/secret.yaml.example`. De waarde zetten is beheer (#941). Aanmaken, zetten en roteren:
  `docs/mcp.md`.
