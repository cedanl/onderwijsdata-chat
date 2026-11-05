### Dashboardcode opgeruimd: lazy geladen, één legenda, geen instellingsnaam op WARNING (#907)
- Een rapport openen laadt de dashboards en Chart.js niet meer mee: de rapportenroute ging van 106 kB naar 23 kB (gzip).
- Een klik op de legenda zet een reeks bij de eerste klik aan of uit, ook bij de peers in "Diplomarendement over tijd"
  die verborgen beginnen; die hadden er twee klikken voor nodig.
- Het log noemt de gevraagde instelling op WARNING alleen nog als lengte en hash; de naam staat op DEBUG.
- `docs/dashboards.md` beschrijft de drie dashboards, hun eindpunten, bronnen (DUO, UWV, ROA; geen CBS) en Chart.js.
