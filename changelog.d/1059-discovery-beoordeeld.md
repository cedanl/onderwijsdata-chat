### Discovery meldt al afgewezen CBS-tabellen niet meer elke week (#1059)
- `cbs:discovery` kent nu een lijst `BEOORDEELDE_TABEL_IDS` met per tabel de reden van afwijzing. Zo'n tabel staat in
  het rapport onder `uitgesloten`, niet meer onder `nieuw_voor_review`. Erin: `83861NED` (bevolking Caribisch
  Nederland) en de vijf SES-tabellen per wijk (`85163NED`, `85539NED`, `85900NED`, `86092NED`, `86296NED`), op 21-10 en
  in #1056 afgewezen. Op de sweep van 18-11 zakt het aantal actieve tabellen voor review van 6 naar 0.
- `docs/operatie.md`: wie een discovery-issue afhandelt, zet afgewezen tabellen in de lijst.
