### De arbeidsmarktmatch noemt bron, peildatum, drempel en definitie bij schaarste en overaanbod (#900)
- `/api/dashboard/arbeidsmarktmatch` geeft `match_duiding`: de drempel (1,2), de peildatum van de UWV-momentopname, de
  diplomajaren van het gemiddelde, de ROA-versie en de herkomst van de sectorindeling (LLM-classificatie, niet van UWV).
- De match-tegels, de grafiek "Gediplomeerden vs. vacatures" en het vacatureaanbod in de regio tonen een banner met de
  peildatum uit de data in plaats van de vaste tekst "mei 2023".
- Onder de tegels staat wat schaarste, overaanbod en evenwicht betekenen, met de drempel, en wat de score niet zegt:
  vacatures hebben geen opleidingsniveau en zijn een stand van één dag tegenover een meerjarig gemiddelde. Een sector
  zonder score staat in een noot in plaats van stil weg te vallen.
