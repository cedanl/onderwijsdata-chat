### Een bronfout noemt de dataset bij naam en de fout in woorden (#1053)
- Kon een rapport een dataset niet opnieuw ophalen, dan noemde de melding de interne key (`duo:p01hoinges:0`) en de
  Python-klassenaam van de fout (`ConnectError`). Nu staat er de catalogustitel van de dataset en een korte omschrijving:
  "DUO gaf de data van 'Ingeschrevenen hoger onderwijs in het domein hoger onderwijs' niet opnieuw: DUO is nu niet
  bereikbaar (verbinding mislukt)." Zonder bekende titel noemt de melding alleen de bron.
- Een bronfout noemt "verbinding mislukt", "time-out", "te veel verzoeken (HTTP 429)" of "onbekende fout" in plaats van
  een klassenaam; de klassenaam staat alleen nog in het log.
