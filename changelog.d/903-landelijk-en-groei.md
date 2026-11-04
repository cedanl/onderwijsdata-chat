### Landelijk zegt wat het telt, groei heeft één basis en het regiogemiddelde zijn aantal (#903)
- Het landelijke dashboard zegt nu dat "landelijk" de som van het DUO-bestand per instelling is, met onderdrukte cellen
  als ondergrens, en dat de chat het landelijke aantal uit een CBS-tabel geeft (85354NED voor het mbo, 85423NED voor het
  ho), dat ervan kan afwijken. Het dashboard rangschikt instellingen en rekent aandelen per sector, wat CBS niet kent;
  daarom blijft het de DUO-som. De API geeft dit in `landelijk`.
- Een test legt de verbinding met de vaste maten van de chat vast: voor een mbo-instelling geven dashboard en
  `get_maat` hetzelfde aantal; voor een ho-instelling wijken ze alleen af in jaren die het dashboard als ondergrens meldt
  (het dashboard en de chat lezen een ander DUO-bestand, dat andere cellen onderdrukt).
- Groei op Mijn instelling heeft één regel: vanaf hetzelfde startjaar voor alle instellingen tot het laatste jaar, in de
  lijngrafieken, de groeiranking en de tabel concurrenten. Het startjaar staat in de kop ("Groei ingeschrevenen
  2022–2025", "% verandering t.o.v. 2022"). Eerder nam elke lijn haar eigen eerste jaar en de ranking per instelling
  haar eerste tot laatste jaar, zodat één instelling op één pagina twee groeicijfers had.
- Het regiogemiddelde noemt het aantal instellingen waarover het in dat jaar gemiddeld is (`benchmark.n_per_jaar`);
  `n_instellingen` telt de peers met data in het laatste jaar, niet alle instellingen van de regio in het register.
