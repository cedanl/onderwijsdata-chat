### Beheer: `audit:python` weer groen, LCSK-melding bij de promotie (#972)
- `audit:python` negeert de tien filelock-CVE's van 26-10 bewust, elk met reden in SECURITY.md S12 (herzien uiterlijk
  06-12-2026, weg zodra litellm `filelock<4.0` loslaat). De job is weer groen, zodat een nieuwe CVE opvalt; een test
  houdt de lijst in de job en in S12 gelijk.
- `scripts/promotie.py promote` meldt bij de eerste promotie die de Studiekeuzedatabase naar playground brengt (na
  2.8.0) dat LCSK binnen drie weken een link of pdf moet krijgen (info@lcsk.nl, art. 4.6 van de leveringsvoorwaarden);
  `docs/promoten.md` heeft er een checklistregel voor.
