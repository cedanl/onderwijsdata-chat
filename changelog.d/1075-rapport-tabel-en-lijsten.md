### Tabellen en genummerde lijsten in de conclusie van een rapport (#1075)
- Een tabel in de conclusie (`| Sector | Instroom |` met een `|---|---:|`-regel eronder) staat in de viewer, de
  HTML-download en de PDF nu als echte tabel, met randen, een vette kop en de uitlijning uit de scheidingsregel; op een
  telefoon scrolt een brede tabel binnen de kaart, en in de PDF breekt geen rij over twee pagina's.
- Genummerde regels (`1.` of `1)`) worden een genummerde lijst, `-`/`*`-regels een opsomming; er staat geen los
  opsommingspunt meer buiten een lijst.
- De Markdown-download en "Download als Word" lezen de nieuwe HTML: de Markdown krijgt de pipetabel en de lijstregels
  terug, Word dezelfde tabel en punten als voorheen. Een ouder rapport leest zoals het las.
