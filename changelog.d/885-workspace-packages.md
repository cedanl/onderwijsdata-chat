### Bronpakketten onderwijsdata en riodata staan in deze repo als uv-workspace (#885)
- De pakketten `onderwijsdata` (v0.2.2) en `riodata` (0.7.0) staan nu onder `packages/`, met hun git-geschiedenis, als
  leden van een uv-workspace. De chat installeert ze niet meer van GitHub maar uit dezelfde commit als de app; `uv.lock`
  en de Docker-build hebben geen git of netwerktoegang tot de pakketrepo's meer nodig. Er verandert niets aan de
  antwoorden: dezelfde pakketcode, dezelfde catalogus (CBS-catalogusrevisie `076d42ee7c5ec9b8`, 268 tabellen).
- De Docker-build kopieert `packages/` vóór `uv sync --no-editable`; de catalogusdata (±14 MB) zit in de `.venv` van het
  image; de venv is even groot (507 MB) en bevat dezelfde pakketbestanden. `git` verdwijnt uit de bouwstap.
- `/version` noemt bij `onderwijsdata` en `riodata` geen `commit` meer (de pakketten komen uit de app-commit; `commit`
  bovenaan blijft). `catalogusrevisie` en `aantal` blijven. Wat /version en de installatieregel in snippets daarna
  per pakket noemen, volgt in #888.
- Ruff, ty en de dekking van de chat slaan `packages/` over (de pakketten hadden als losse repo's geen lint of
  typecontrole); hun eigen tests (263 en 277) slagen in de workspace en komen in CI met #886. Na deze wijziging moet
  elke lokale `.venv` opnieuw `uv sync` draaien.
