### De CSV bij een grafiek of kaart noemt de inhoudshash of de DUO-md5, net als de tabel-CSV (#809)
- De CSV-knop bij een grafiek zette bron, selecties en afronding boven de kop, maar niet de inhoudshash (CBS, RIO) of
  de md5 van het DUO-bestand die de tabel-CSV wel had (#715, #717). Ook afkap en onderdrukte cellen ontbraken. Eén
  functie (`tools/exportnoten.py`) geeft nu de herkomstregels voor de tabel-CSV, de grafiek en de kaart; de kaart had
  er nog geen.
