### Een CBS-combinatie die niet bestaat, maakt een totaal geen ondergrens meer (#1213)
- Een lege CBS-cel ('.') maakte elk totaal erover een ondergrens, ook als de cel een combinatie is die niet bestaat:
  85424NED kent geen hbo-associate degree binnen het wo, en die cel is in elk jaar leeg. Het Telling-blok zei dan
  "ondergrens" terwijl de som volledig was. Een combinatie van dimensiewaarden die in elk jaar van de geladen tabel leeg
  is, telt nu niet meer als onderdrukte cel: geen Ondergrens-regel, geen noot in de tool-output en geen ondergrens in de
  CSV-kop. Een cel die maar in sommige jaren leeg is, blijft een onderdrukt cijfer en dus een ondergrens.
- Bij een lading van één jaar, of zonder bekende dimensies, valt dat niet te zien: dan blijft elke lege cel onderdrukt.
  Omgekeerd leest een cel die in elk geladen jaar onderdrukt is (een heel kleine gemeente) als een combinatie zonder
  cijfer.
