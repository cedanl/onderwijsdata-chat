### Onder elk data-antwoord: "Wat is gecontroleerd" (#1260)
- Een ingeklapte regel zegt hoeveel getallen tegen de opgehaalde data zijn gelegd, of schooljaar en instelling zijn
  nagelopen, welke controle niet kon draaien en hoe vaak het antwoord na de controle is gecorrigeerd. Zonder getallen
  staat er "Geen getallen om te controleren".
- De regel zegt altijd ook wat níét gecontroleerd is, in een vaste zin, en belooft niets wat de controle niet doet.
- Alles komt uit code: wat het model over zijn eigen controle schrijft, verandert de regel niet. De regel staat ook in
  de kopie, de gespreksexport, de kop van elke CSV en het bewijsbestand "Bewijs (JSON)" (#1244): de sleutel `controles`
  heeft de regel en de tellingen waar ze op rust.
