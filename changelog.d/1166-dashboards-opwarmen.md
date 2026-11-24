### Dashboards na een herstart meteen snel (#1166)
- Na een start laadt de app de bronnen van de dashboards op de achtergrond, zodat de eerste gebruiker van Mijn
  instelling niet meer 10-23 seconden wacht. De start zelf wacht er niet op. `DASHBOARD_WARMUP=false` zet het uit.
