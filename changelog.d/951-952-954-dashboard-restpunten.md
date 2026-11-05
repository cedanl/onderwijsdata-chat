### Vaste dashboards: regiototaal, kleine sectoren in de match en het oude instroom-pad (#951, #952, #954)
- "Regio totaal" telt de eigen instelling mee en zegt wie erin zit: "Curio en 6 andere mbo-instellingen in provincie
  Noord-Brabant" (72.104), in plaats van 56.816 zonder Curio naast "6 instellingen in regio". Het marktaandeel rekent
  met hetzelfde totaal. Het rendement noemt in zijn label de peers in het gemiddelde, niet de gevonden peers, en heeft
  een korte legenda; de definitie zegt dat teller en noemer ondergrenzen zijn.
- Curio staat op haar eigen kaart (Etten-Leur ontbrak, net als vijf andere plaatsen). Het mbo krijgt bij
  "Gediplomeerden per jaar" het regiogemiddelde dat de grafiek beloofde. De ROA-prognose toont de verwachte
  baanopeningen en instroom van schoolverlaters (stonden overal als "—"). Het UWV-blok heet "in de provincie".
- Elke liggende staafgrafiek noemt elke categorie (Chart.js sloeg er de helft over), lange woorden breken af op een
  telefoon, sectoren en leerwegen heten bij hun naam (geen GEDRAG_EN_MAATSCHAPPIJ of BOLVT), een aandeel vrouw staat
  op één decimaal en "ten minste" staat overal hetzelfde voor het getal.
- Arbeidsmarktmatch: een sector met minder dan 30 gediplomeerden per jaar krijgt geen label en geen verhouding maar
  "te weinig gediplomeerden"; een staaf is hoogstens 5 lang, met de echte waarde in tooltip, tabel en een noot
  (Tilburg University, Techniek: 52,15). De duiding zegt dat teller en noemer verschillende grootheden zijn.
- `GET /api/dashboard/instroom` geeft 410 met waar de cijfers nu staan, en elk ander pad onder `/api/dashboard/` of
  `/api/dashboards` 404 met de vier eindpunten, in plaats van een kale 404.
