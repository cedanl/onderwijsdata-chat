### Catalogus: de periode van een CBS-tabel loopt niet meer achter op de tabel (#1070)
- Bij 47 actuele CBS-tabellen eindigde de periode in de catalogus een of meer jaren vóór de laatste periode van de
  tabel zelf: 85776NED stond op "2006/'07-2022/'23" terwijl de tabel tot 2023/'24 loopt. De periode staat in de
  zoektreffer, op de Databronnen-pagina en in antwoorden die haar noemen.
- De wekelijkse controle haalt nu naast de wijzigingsdatum ook de periodetekst bij CBS. Zegt CBS de tekst zelf niet
  bij (85566NED noemt 2024/'25 terwijl de tabel tot 2025/'26 loopt, 85379NED begint volgens de tekst in 2021/'22 maar
  in de tabel in 2011/'12), dan volgt de tekst de perioden van de tabel.
- `perioden_verouderd` in `/version` telt nu ook een actuele tabel waarvan de periodetekst achterloopt, en een test
  over de hele catalogus faalt bij een verschil.
- De periode van de vo-contexttabellen in `docs/databronnen.md` volgt de catalogus; een test bewaakt dat.
