"""De gedeelde kern van de bronnen (#910, #911): alles wat meer dan één bron nodig heeft.

- `resolutie`: één resource kiezen uit de bestanden van een dataset (ID, index, naam), met de foutsoorten.
- `lezen`: CSV-downloads lezen, met een eigen fout per stap en de herkomst (checksum, bytes).
- `verrijking`: bronmetadata en verrijking samenvoegen tot één catalogusrecord, en pakketdata lezen.
- `broncontract`: de metadatavelden die elke bron levert, en wat "niet te leveren" betekent.
- `bron_id`: het ID-contract `bron:id` (`BronId.parse`/`normaliseer`, `Register`), #912.
- `bestuur`: het bestuursnummer als één sleutel (`Bestuurssleutel`), met het BRIN-suffix van 40833 (#935).
- `sleutels`: de koppelsleutels die bronnen delen (brin, croho, gemeente, schooljaar, …) met hun kolomnamen en een
  pure normalisatie; per catalogusrecord `_sleutels` (#958). Publiek als `onderwijsbronnen.sleutels`.
- `versie`: de ene versie van het pakket.

De kern importeert nooit een bron; een bron importeert alleen de kern (tests/test_importgrens.py in de chat).
"""
