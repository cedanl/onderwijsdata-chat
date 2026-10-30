### Een logregel per modelaanroep, om de time-out per aanroep op meting te kiezen (#800)
- De time-out per modelaanroep (`LITELLM_REQUEST_TIMEOUT`, 1200 s) ligt boven elke grens per run, zodat een nieuwe
  poging na een time-out er nooit in past. Een lagere waarde kan alleen op meting. Elke modelaanroep logt nu één
  regel `MODELAANROEP` (INFO), zonder gebruikerstekst: model, uitkomst (`ok`, `gestopt` of het fouttype), de seconden
  tot de provider antwoordde, tot de eerste chunk en tot het einde, en de uitvoertokens. De waarschuwing bij een
  time-out noemt hoe lang de poging liep.
- `LITELLM_REQUEST_TIMEOUT` staat nu in `docs/configuratie`. De waarde verandert pas na een week meten.
