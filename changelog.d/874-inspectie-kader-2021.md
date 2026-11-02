### Inspectie-oordeel toont de standaarden van het onderzoekskader 2021 (#874)
- `get_inspectieoordeel` gaf bij de meeste mbo-besturen geen enkele standaard, ook als de Inspectie er drie had
  vastgesteld: de tool las alleen de kolommen van het kader 2017. Nu leest ze per onderzoekskader de juiste kolommen.
  Onder het kader 2021 zijn dat Visie, ambities en doelen; Uitvoering en kwaliteitscultuur; en Evaluatie,
  verantwoording en dialoog. Op 1 oktober 2026 kregen 138 van de 164 mbo-besturen geen standaarden, nu nog 26: 25
  besturen zonder kader (onderzoeken van voor 2021) en één zonder ingevulde standaarden.
- De uitkomst noemt het onderzoekskader, omdat standaarden uit verschillende kaders niet te vergelijken zijn. Bij het
  kader 2017 staan de oordelen per kwaliteitsgebied (financieel beheer, kwaliteitszorg en ambitie) apart van de
  standaarden.
- Een onbekend kader of een nieuwe kolom in het bestand van de Inspectie komt als `INSPECTIE_KADER_ONBEKEND` in het
  log, en de tool zegt dan dat ze de standaarden niet toont.
