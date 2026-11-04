### De dashboards houden een onderdrukte of ontbrekende cel gescheiden van 0 (#902)
- Een totaal, gemiddelde of regiototaal waarin een onderdrukte DUO-cel valt (DUO publiceert kleine aantallen niet),
  zegt nu "ten minste": in de kerncijfers van Mijn instelling, in de landelijke ranking en in een noot onder de
  kerncijfers per reeks, met de jaren. De API geeft per reeks het aantal lege cellen per jaar in `onderdrukt`, ook voor
  het regiogemiddelde (`benchmark.onderdrukt`).
- Een jaar of sector zonder waarde is een gat in de grafiek, geen val naar 0: in de sectortrend, de leerweggrafiek, de
  eigen sectoren op het landelijke dashboard en het aandeel vrouw. Een jaar met alleen onderdrukte cellen krijgt geen
  waarde meer in plaats van 0. Een pseudocohort zonder diplomajaar heeft `null`, geen 0.
- Een positie landelijk waarin een onderdrukte cel meetelt, heet "indicatief"; een sector zonder eigen ingeschrevenen
  krijgt geen positie en wordt genoemd (`positie_weggelaten`).
- Wat een grafiek of tabel weglaat, staat eronder: de sectoren zonder gediplomeerden in "Gediplomeerden vs. vacatures"
  (nu aflopend op gediplomeerden), de sectoren zonder waarde in "Marktaandeel per sector" en de pseudocohorten met meer
  gediplomeerden dan instroom of zonder diplomajaar.
- Het regio- en het instroomdashboard rekenen hun reeksen met dezelfde functies (`_ho_kern`, `_mbo_kern`), en het
  landelijke dashboard rekent ho en mbo met één functie (`_nationaal_cijfers`).
