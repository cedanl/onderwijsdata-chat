### Een bron die niet live is, staat bij het openen van de app (#1057)
- De app meet elke twee minuten vanuit de pod of CBS, DUO, RIO, UWV en de inspectie antwoorden. Antwoordt een bron niet
  (ook niet bij een directe tweede poging), dan staat er bij het openen van de app een melding boven de pagina, bijvoorbeeld
  "DUO is op dit moment niet bereikbaar. Antwoorden die DUO-data nodig hebben kunnen falen of ontbreken." Zijn alle bronnen
  live, dan staat er niets. De melding verdwijnt zelf zodra de bron weer antwoordt.
- Nieuw eindpunt `GET /api/bronstatus` en instelling `BRONSTATUS_INTERVAL_S` (0 zet de meting uit). Zie `docs/operatie.md`.
