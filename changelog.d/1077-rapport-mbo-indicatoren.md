### Rapport: cijfers uit `get_mbo_indicatoren` worden niet meer geweigerd (#1077)
- Een rapport over het diplomaresultaat of de vsv van een mbo-instelling werd altijd geweigerd ("Deze percentages staan
  niet in de opgehaalde data"), ook als de chat de getallen letterlijk uit `get_mbo_indicatoren` had. Die tool legt niets
  in de store, dus telde de rapportcontrole haar uitvoer niet als bewijs. Nu bewaart de sessie die uitvoer als bewijs (zoals
  het rekenbewijs van `compute_kpi`), met het nummer van de vraag waarbij ze ontstond. De controle telt de getallen erin,
  het rapportmodel ziet de uitvoer in zijn prompt, en een getal dat er niet in staat blijft geweigerd.
- De bronregel van de mbo-indicatoren ("DUO · Indicatoren per instelling (jaardocument mbo), editie …, peildatum …")
  staat onder Bronnen als het rapport een getal uit die uitvoer noemt.
- De checklist bij "Genereer rapport" toont een beurt met alleen die tool nu, met haar bron, en het bewijs gaat alleen mee
  als de gebruiker die beurt aanlaat. Bij heropenen volgt het nummer van de vraag de plaats van het antwoord.
