### Operatie: wekelijkse kwaliteitsaudit uit tellers en logregels, zonder gebruikerstekst (#1250)
- Vijf nieuwe Prometheus-tellers in `GET /metrics`: `edudata_controle_uitkomsten_total{controle,uitkomst}`,
  `edudata_herkansingen_total`, `edudata_ingehouden_antwoorden_total`, `edudata_stappenbudget_op_total` en
  `edudata_tool_weigeringen_total{tool,reden}`. De labels komen uit vaste lijsten (de controles en tools van de app,
  vaste woorden); een andere naam telt als `overig`.
- `scripts/kwaliteitsaudit.py` maakt uit die tellers of een logexport een weekrapport: aantallen per controle en per
  tool, de trend tegen de vorige week, de top 10 van wat misgaat en kandidaat-wijzigingen. Het leest alleen vaste
  regelsoorten, neemt geen vraag- of antwoordtekst over, roept geen model aan en opent of merget geen MR. Een voorstel
  gaat altijd via een MR met review. Inplannen is een latere stap van een beheerder (`docs/operatie.md`).
