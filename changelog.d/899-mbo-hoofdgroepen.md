### De mbo-cijfers in de dashboards heten wat ze tellen (#899)
- "Studenten per SBB-sectorkamer" in Mijn instelling heet nu "Ingeschrevenen per hoofdgroep". Het getal is `TOTAAL MBO`
  uit DUO's instromende mbo-studenten: ingeschrevenen, nieuw of niet (domeinregel `mbo-instroom-totaal-mbo`). De
  ondertitel noemde het eerstejaars, en het zijn DUO-hoofdgroepen, geen SBB-sectorkamers. Het veld heet
  `ingeschrevenen_per_hoofdgroep` (was `sectorkamers`).
- De arbeidsmarktmatch van een mbo-instelling zet nu gediplomeerden per hoofdgroep tegenover de vacatures, gemiddeld
  over de laatste drie diplomajaren, zoals bij het ho. Tot nu toe stonden er ingeschrevenen in het veld
  `gediplomeerden_per_sector`, in de testdata drie tot vier keer zoveel als de gediplomeerden.
- De leerwegverdeling van het regiodashboard telt Extraneus mee, net als het instroomdashboard: de leerwegen tellen nu
  in beide op tot het totaal ingeschrevenen. De grafiek "Leerweg-verdeling over tijd" toont Extraneus als vierde laag.
