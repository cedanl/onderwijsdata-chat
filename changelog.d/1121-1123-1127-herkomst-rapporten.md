### Een Word-rapport draagt de eigenschappen van het rapport, niet van het sjabloon (#1121)
- Aanmaak- en wijzigdatum van het gedownloade Word-document zijn het moment van renderen (UTC), en auteur en "laatst
  gewijzigd door" zijn de opsteller uit het rapport; zonder opsteller blijven ze leeg. Eerder stond er de datum van het
  sjabloon (18-11-2026) en de toolnaam, zodat een rapport in Verkenner of een documentbeheersysteem op de verkeerde datum
  stond. De opmaak van het Npuls-sjabloon verandert niet.

### De herkomst van een rapport noemt de commit, niet alleen de appversie (#1123)
- De verantwoordingsregel van een rapport (en van de gespreksexport) toont achter de appversie de korte commit van de
  build, bijvoorbeeld `app 2.8.0 (commit 7d3488aa)`, dezelfde als in `/version`. Test volgt main met een open range, dus
  twee builds met dezelfde versie waren in een rapport niet uit elkaar te houden. Word en Markdown nemen de regel
  ongewijzigd over. Zonder `GIT_COMMIT` (lokaal) blijft de regel zoals ze was, zonder "onbekend".

### Een afgedrukt dashboard heeft een kop met naam, instelling, datum en productnaam (#1127)
- "Afdrukken of als pdf bewaren" op een vast dashboard begint nu met dezelfde Npuls-printkop als de rapport-PDF: het
  logo met "EDUdata", de naam van het dashboard, de instelling en "Afgedrukt op" met de datum van het afdrukken (niet van
  het openen van de pagina). Een geprinte dashboard-PDF is zo te dateren en te herleiden. Op het scherm verandert niets.
