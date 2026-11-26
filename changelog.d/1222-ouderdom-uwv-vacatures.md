### Arbeidsmarkt: hoe oud de UWV-vacatures zijn, en waar de actuele staan (#1222, #1219, #1220)
- De dashboards, de chat en de bronregels noemen naast de UWV-peildatum hoe oud ze is: "peildatum 16 mei 2023 (ruim
  3 jaar geleden)" in de banner, "peildatum 16 mei 2023, ruim 3 jaar oud" in de ondertitels, het bronblok en de
  bronregel onder een chatantwoord.
- Is de peildatum meer dan 12 maanden oud, dan is de banner een waarschuwing: UWV werkt deze open dataset sinds mei
  2023 niet meer bij, en UWV (dashboard Vacaturemarkt) en CBS (tabel 83599NED) publiceren de actuele vacatures per
  kwartaal, met links. De app laadt die niet.
- De ouderdom komt van de server (`peildatum_ouderdom_maanden` en `verouderd` in `vacatureaanbod`, `match_duiding`, het
  bronblok en het resultaat van `get_uwv_vacatures`); het model noemt haar bij een verouderde stand ook in het antwoord.
- Zonder vacatures noemt het UWV-blok de peildatum of de periode van de UWV-catalogus, geen vaste maand.
- `docs/databronnen.md` beschrijft UWV Open Match zoals het is: via data.overheid.nl, CC BY 4.0, vacatures en
  werkzoekenden per beroep(encluster) en regio, wekelijkse momentopnamen tot 16-05-2023, met de reden van UWV en waar
  de actuele kwartaalcijfers staan.
