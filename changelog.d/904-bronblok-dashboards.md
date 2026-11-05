### De dashboards noemen hun bronnen uit de payload, met versie, peildatum en voorlopige jaren (#904, deel 1)
- Elk dashboard-eindpunt geeft een bronblok (`bronnen`): per gebruikte bron de dataset, de titel en link uit de
  catalogus, de versie of editie, de peildatum, of er voorlopige cijfers in zitten en wanneer de app de bron ophaalde.
  DUO met resource-ID en `last_modified` per bestand ("versie van 08-04-2026", zoals de bronregel in de chat), UWV met
  de peildatum van de momentopname, ROA met de editie en de versie uit het bestand.
- Het blok komt uit wat de lading echt laadde: een bron die niet laadde, staat er niet in (wel in `niet_beschikbaar`),
  en een mbo-dashboard noemt de ho-bestanden niet waarin de app eerst naar de naam zocht. Landelijk en Arbeidsmarkt
  laden van het ho alleen de bestanden die ze gebruiken.
- De footer, de bronbadge en de ROA-teksten bij de grafieken tonen dit blok in plaats van vaste lijsten per dashboard;
  de ROA-teksten noemen nu de editie uit de data.
