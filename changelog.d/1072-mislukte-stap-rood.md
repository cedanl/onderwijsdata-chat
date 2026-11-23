### Een mislukte toolstap staat niet meer groen in de redeneerkaart (#1072)
- Een opvraag van een onbekende CBS- of DUO-tabel, een vaste maat voor een onbekende instelling, een KPI over een kolom
  die niet bestaat en een analyse die de tijdgrens haalde stonden als geslaagd ("CBS data opgehaald", "KPI berekend",
  "Analyse uitgevoerd"), met eronder een codefragment dat de mislukte aanroep herhaalde. Nu staan ze rood met een eigen
  melding ("CBS-opvraag mislukt", "KPI-berekening mislukt", "Analyse mislukt") en zonder codefragment. Ook een andere
  stap met een gecodeerde bronfout ("Stap mislukt") staat niet meer groen.
