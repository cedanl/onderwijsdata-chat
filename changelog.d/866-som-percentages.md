### Geen som meer over percentages; een gemiddelde is geen ondergrens (#866)
- `query_data` en `compute_kpi` telden elke getallenkolom op, ook een percentage: een som over de %-kolom van een
  CBS-tabel of over een DUO-kolom met PERCENTAGE of AANDEEL in de naam gaf een getal zonder betekenis. Nu weigeren
  ze die som, en ook een som over een mutatie, saldo, verschil of groei, met uitleg hoe het wel kan: tellers en
  noemers apart optellen, of een gemiddelde met de kanttekening dat het ongewogen is. De eenheid komt uit CBS, anders
  uit de kolomnaam.
- Een gemiddelde (of minimum, maximum, telling) over onderdrukte cellen heette ten onrechte een ondergrens. Nu zegt
  de noot dat het gemiddelde zonder die cellen is berekend, en noemt het Telling-blok zo'n uitkomst geen ondergrens.
