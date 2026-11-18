### Chat: query_data rekent een gewogen gemiddelde per groep (#1017)
- `query_data` kent de aggregatie `weighted_mean` met een nieuwe parameter `weights`: per groep som(waarde × gewicht) /
  som(gewicht), bijvoorbeeld het NSE-oordeel per instelling gewogen naar het aantal respondenten. Twee vestigingen met
  3,5 (100 respondenten) en 4,0 (300) geven 3,875, niet het ongewogen 3,75.
- Een rij met een lege, onleesbare of onderdrukte waarde of gewicht telt niet mee; de noot zegt hoeveel rijen. Een
  groep zonder bruikbare rij, of met gewichtssom 0, is leeg (null), nooit 0. Een ontbrekend, onbekend, niet-numeriek
  of negatief gewicht, of een gewicht in `group_by`, geeft een melding en geen nieuwe key; de app kiest nooit zelf een
  gewicht.
- Zo gaat de vraag uit de reaudit (N07) zonder eigen pandas: aggregeer elke bron eerst met `query_data` per
  instelling (`weighted_mean` voor scores, `sum` voor aantallen) en koppel daarna met `koppel_data`. De prompt, de
  waarschuwing van `koppel_data` bij korrel many en de melding bij een som over een percentage wijzen die route.
- De snippet rekent teller en noemer per groep zichtbaar uit en geeft hetzelfde getal als de app. Een selectie zonder
  `weights` houdt haar bestaande data_key.
