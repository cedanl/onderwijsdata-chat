### Een ongeldige LOG_LEVEL stopt de start met een melding, niet met een traceback (#1163)
- `Config.validate()` controleert nu ook `LOG_LEVEL`. Een waarde buiten `DEBUG`, `INFO`, `WARNING`, `ERROR` en
  `CRITICAL` stopt de start met één logregel (JSON buiten `APP_ENV=local`) die de geldige waarden noemt, in plaats van
  een Python-traceback van ± 50 regels. Kleine letters (`info`) blijven werken, en een lege waarde is `INFO`.
- Een configuratiefout staat daarbij één keer in het log: `validate()` logde elke fout zelf en `server.py` daarna de
  samengevoegde melding.
