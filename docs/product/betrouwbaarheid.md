---
icon: lucide/shield-check
---

# Een antwoord lezen en controleren

Een taalmodel formuleert het antwoord, maar code controleert de getallen tegen de data die de app heeft opgehaald. Deze pagina zegt wat je onder een antwoord ziet en wat de controle wel en niet doet. Het technische verhaal staat in [Kwaliteit & veiligheid](../kwaliteit-en-veiligheid.md) en [Anti-hallucinatie architectuur](../anti-hallucination-architecture.md).

## Wat je onder een antwoord ziet

| Je ziet | Wat het zegt |
|---|---|
| **Uitgangspunt:** (bovenaan een dataantwoord) | Wat er geteld is: jaar, opleidingsvorm en dergelijke. |
| **Niet meegeteld:** | Wat buiten het getal valt. |
| **Bronnen** | Elke dataset die het antwoord las, met titel, periode en dataset-ID. Elke regel is een link naar de bronpagina. Een CBS-regel noemt ook de dag waarop CBS de tabel het laatst bijwerkte en de dag waarop de app hem ophaalde. |
| **Let op: …** | Een zachte bevinding van de controle, zoals een label of teleenheid die niet klopt. Het antwoord blijft staan. |
| **Wat is gecontroleerd** | Wat de code toetste, en altijd wat ze níet toetst (zie hieronder). |
| **Ter controle:** | Voor een deel van de maten het getal van een tweede bron, met het verschil en de bekende redenen. |
| "voorlopig cijfer" | CBS kan het cijfer nog herzien. Soms staat er ook een verwachte datum van de volgende editie. |
| "ten minste" of "≥" | De bron publiceert kleine aantallen niet, dus het getal is een ondergrens. |

## Als de controle iets vindt

- Een **hard** probleem, zoals een getal dat niet in de data staat, een verkeerd schooljaar of een verkeerde instelling: het antwoord wordt ingehouden of aangepast. Je ziet dan "Eerste versie van dit antwoord is aangepast na controle".
- In de chat kan een zin of tabelrij met zo'n getal vervallen. De app meldt dan: "Zinnen met een getal dat niet in de opgehaalde data staat, zijn weggelaten."
- Een **zacht** probleem: het antwoord blijft, met "Let op: …" eronder.

## Wat de controle niet dekt

De controles zijn code, geen begrip. Onder elk dataantwoord staat deze vaste zin:

> Niet gecontroleerd: of de bron zelf klopt, getallen onder de duizend en jaartallen, conclusies en verbanden die niet uit de cijfers volgen, en bij welke groep een getal hoort als de zin of tabelrij geen jaar of instelling noemt.

Controleer dus zelf of een conclusie uit de cijfers volgt, en bekijk de bron als het getal ertoe doet.

## Zelf nagaan

- Klik de link bij een bron naar de bronpagina.
- Met **Geavanceerd** (Instellingen) staat bij elke stap de Python-code waarmee je de analyse zelf herhaalt ([Reproduceerbare analyses](../reproducibility.md)).
- Met "Bewijs (JSON)" download je het bewijs van een dataantwoord: de antwoordtekst, de bronnen, de controlemeldingen en per toolstap de tool, haar argumenten en de code. Je browser maakt het bestand uit het antwoord dat op je scherm staat; er gaat niets naar de server.
- Per release meet CEDA hoe vaak de assistent bronwaarheid-vragen goed beantwoordt: [Betrouwbaarheid per release](../betrouwbaarheid.md).
