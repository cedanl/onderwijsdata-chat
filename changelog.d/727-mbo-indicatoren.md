### Jaarresultaat, diplomaresultaat en vsv per mbo-instelling, met vergelijkingsgroep (#727)
- De chattool `get_mbo_indicatoren` geeft per mbo-instelling het jaarresultaat, het diplomaresultaat en het
  percentage nieuwe vsv'ers over drie schooljaren, elk naast de waarde van de vergelijkingsgroep (alle roc's of alle
  beroepscolleges). De bron is DUO's bestand met indicatoren per instelling (geïntegreerd jaardocument), alleen de
  nieuwste editie, één keer per dag opgehaald. De code rondt af en berekent het verschil in procentpunt.
  - Het laatste vsv-jaar heet voorlopig. Een lege cel of een 0 in het bestand wordt "geen cijfer", zonder getal.
  - De cijfers gelden per BRIN: staat dezelfde naam ook onder een andere BRIN (Curio), dan zegt een noot dat ze niet
    samen te nemen zijn.
  - Hbo en wo krijgen een vaste melding; de sheet `Financieel` blijft bij #725.
- De kolommen komen uit de koppen, niet uit vaste posities. Een onbekende kop, sheet, BRIN of vergelijkingsgroep, een
  percentage buiten 0–1 of een groepswaarde die binnen een groep verschilt (verwisselde kolommen) geeft een
  foutmelding zonder cijfers, net als een HTML-foutpagina met HTTP 200 (soft 404).
- Onder het antwoord staat "DUO · Indicatoren per instelling (jaardocument mbo), editie …, peildatum …", met een link
  naar het bestand. `bron:ping` haalt de editie ook op.
- De prompt stuurt vsv per instelling naar deze tool en vsv landelijk naar CBS; de twee cijfers zijn niet vergelijkbaar.
