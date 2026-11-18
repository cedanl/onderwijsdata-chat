### /version noemt de catalogus-digest uit het manifest (#1029)
- `/version` heeft een nieuw veld `catalogus_digest`: de digest van de catalogus die het proces geladen heeft, met zijn
  bronvlaggen (SKDB, WOPI, financiën). Dat is dezelfde waarde als `catalogus` in het manifest van een antwoord en in de
  logregel `GEPUBLICEERD`, zodat het ID uit een manifest nu tegen de draaiende omgeving te controleren is. Laadt de
  catalogus niet, dan is het veld `null` en blijft `/version` werken.
- `catalogusrevisie` onder `catalogus` blijft wat het was: welk CBS-artefact is meegebouwd. `docs/api.md` legt het
  verschil uit.
