### De Python-snippet laadt precies wat de app laadde, voor elke tool (#945, #946)
- De laadstap in een snippet is nu de aanroep die de app deed, niet wat het model als argument gaf. Bij DUO laadt de
  snippet het bestand dat de app koos: ook bij een bestandsnaam, een resource-ID of geen resource (dan het leidende
  bestand, eerder index 0), en met de dataset-ID zoals de catalogus hem schrijft (`duo:p01hoinges` of `P01HOINGES`
  werd letterlijk overgenomen). Bij RIO staat de peildag (`datumGeldigOp`) nu ook in de snippet van `get_rio_data`
  zelf, niet alleen in die van een vervolgstap.
- Bij CBS vraagt de snippet dezelfde kolommen als de app: een selectie van onderwerpen (`$select`) kreeg in de app de
  dimensies erbij, in de snippet niet, waardoor bijvoorbeeld de snippet van een vaste maat zonder `Perioden` laadde.
  Een snippet op een data_key in een andere spelling (`DUO:P01HOINGES:1`) vindt nu ook zijn laadstap.
- Een nieuwe test zet per tool de app en de snippet naast elkaar op dezelfde invoer en vergelijkt de aanroepen van de
  bronladers; een nieuwe tool zonder zo'n geval maakt de test rood.
- Opgeslagen snippets van vóór 2.7.0 met een DUO-resource als tekst-getal (`duo.load("p01hoinges", "4")`, #944): 70
  op test en 132 op playground, alleen in gesprekken, niet in rapporten. Ze laden geen ander bestand maar stoppen met
  `ResourceNietGevonden`; vervang `"4"` door `4`, of stel de vraag opnieuw.
