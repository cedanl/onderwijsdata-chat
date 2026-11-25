### Metrics voor de productiemonitoring, en de SRAM-gegevens in de database (#678, #984)
- `GET /metrics` geeft de metrics van de pod in het formaat van Prometheus: HTTP-verzoeken, duur en 5xx per route,
  open chatverbindingen en lopende runs, modelaanroepen (aantal, fouten, duur, tijd tot de eerste chunk, tokens),
  sandboxruns en time-outs, geweigerde verzoeken per limiet en het aantal keren dat een limiet zonder database telde.
  Het eindpunt bestaat alleen met `METRICS_TOKEN` in het secret en vraagt dan dat token als bearer; zonder token 404.
  Geen label noemt een gebruiker of een vraag. De SLO's en alertvoorstellen staan in "Kwaliteit & veiligheid" (#678).
- Naam, e-mail en organisatie uit SRAM staan tijdens de sessie in de database (`oidc_gebruikers`) in plaats van in het
  geheugen van de server: een herstart of een tweede server kent ze nog. Zelfde grenzen als eerder (24 uur, hooguit
  1000 accounts); uitloggen, "verwijder al mijn gegevens" en de nachtelijke opschoning halen ze weg (#984).
- De tellers van wat er tegelijk mag (verbindingen, runs, sandbox) blijven bewust per server; het besluit staat in
  ADR-011 en "Operatie" (#984).
