### Pagina "Actualiteit van de bronnen" (#1266)
- Nieuwe pagina `/bronnen` (link onderaan de startpagina): per bron (CBS, DUO, RIO, UWV, ROA, SKDB) en dataset de laatste
  periode of editie, de laatste wijziging, de status (voorlopig of definitief), de frequentie en een verwachte volgende
  editie. Die laatste staat er alleen als de bron haar zelf noemt, met die bron erbij; de app raadt geen datum uit de
  frequentie. UWV toont de leeftijd van de stand in dezelfde woorden als de dashboards (#1219).
- Nieuw eindpunt `GET /api/bronactualiteit` (openbaar) en MCP-resource `onderwijscatalogus://bronactualiteit` met
  dezelfde inhoud. Uit de catalogus, zonder verzoek naar een bron; een bron die niet antwoordt staat er als "niet
  bereikbaar".
- Onder een antwoord met voorlopige CBS-cijfers staat de regel "Let op: voorlopig cijfer", en "Nieuwe editie verwacht
  op …" als CBS zelf een dag binnen 30 dagen noemt. Zie `docs/databronnen.md`.
