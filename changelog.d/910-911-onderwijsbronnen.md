### Eén bronpakket: onderwijsbronnen, met een grens tussen de bronnen (#910, #911)
- De bronpakketten `onderwijsdata` (CBS) en `riodata` (RIO, DUO, ROA, UWV, Inspectie, SBB) zijn samengevoegd tot één
  pakket `onderwijsbronnen`, met per bron een subpakket (`cbs`, `duo`, `rio`, `roa`, `uwv`, `inspectie`, `sbb`) en de
  gedeelde code in `_kern`. De chat werkt hetzelfde: zelfde catalogus, zelfde bronkeuze, zelfde waarden die het model
  ziet. Het pakket heet in `/version` nu `onderwijsbronnen` (versie 0.8.0).
- Een nieuwe snippet importeert `from onderwijsbronnen import duo` (CBS: `from onderwijsbronnen.cbs import data`) en
  installeert `#subdirectory=packages/onderwijsbronnen`. Oude snippets blijven werken: ze installeren hun eigen commit,
  en `riodata`/`onderwijsdata` bestaan tijdens de overgang nog als shim met een waarschuwing.
- Een test bewaakt dat een bron nooit een andere bron importeert, alleen `_kern`, en dat elke bron dezelfde metadata
  levert (bron, ID, titel, peildatum of editie, voorlopig, laatste update), met een reden als een veld ontbreekt.
