### `/mcp` op test: `APP_URL` en een runbook voor de sleutel (#941)
- `manifests/test/values.yaml` zet `APP_URL` op de testapp, zodat `vervolg` in een `/mcp`-resultaat naar test wijst in plaats
  van naar playground. `tests/test_manifests.py` toetst dat hij gelijk blijft aan de host van de ingress.
- `docs/mcp.md` beschrijft hoe de beheerder de sleutel op test zet (`sops set`, MR, rollout restart) en hoe de controle
  met de MCP Inspector gaat. De sleutel zelf zet de beheerder buiten een LLM-sessie; zonder sleutel geeft `/mcp` op test 404.
