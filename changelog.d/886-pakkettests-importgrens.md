### De pakkettests draaien in CI en een test bewaakt de grens tussen pakket en chat (#886)
- De CI-job `pytest` draait nu ook de eigen tests van `onderwijsdata` en `riodata` (`packages/*/tests`), elk pakket in
  zijn eigen map en vóór de chattests. Tests met netwerk staan achter `RIODATA_LIVE=1`, zoals in de pakketrepo's, en
  slaan in CI over. Een rode pakkettest blokkeert de MR en de Docker-build net als een rode chattest.
- Nieuwe test `tests/test_importgrens.py`: niets onder `packages/` importeert de chat (`tools`, `agent`, `core`,
  `routes`, `persistence`, …), de twee pakketten importeren elkaar niet (nu ook niet), en de chat importeert alleen de
  publieke API van de pakketten (geen pad met underscore). Een opzettelijke overtreding maakt de job rood, met bestand
  en regel in de melding.
- Ruff en ty slaan `packages/` bewust over (248 ruff-bevindingen, 93 bestanden die anders zouden worden opgemaakt, 93
  ty-diagnostics); de reden en de route om dat per pakket op te ruimen staan in `CONTRIBUTING.md`. `Agents.md` noemt
  waar broncode hoort: bronlogica in `packages/`, beleid in `tools/`.
