### Een herziene tussentabel blijft niet in het antwoord staan (#982)
- Gaf het model eerst een tabel, zei het daarna zelf dat die een vergissing was en gaf het een tweede tabel, dan bleven
  beide in het antwoord staan (F3, diplomaresultaat ROC Midden Nederland). Nu gaan de foute tabel en de correctiezin
  naar de redeneerkaart en staat alleen de laatste tabel in het antwoord. Is er geen tabel die de foute vervangt, dan
  schrijft het model het antwoord opnieuw op.
- Een percentage in een tabelrij wordt nu getoetst aan het schooljaar van die rij, en aan de maat en de instelling of
  vergelijkingsgroep van de kolom. 70,6% bij 2022/23 was het diplomaresultaat van 2024/25 (en het jaarresultaat van
  2022/23); de controle keek alleen of het getal ergens in de bron stond. Zo'n rij geeft nu een herkansing en, als ze
  blijft, een melding onder het antwoord. Dit geldt voor de mbo-indicatoren en het collegegeld (bronnen die een
  schooljaar meegeven), en alleen in tabellen.
- Percentages uit de mbo-indicatoren krijgen een citatie met maat, instelling of vergelijkingsgroep en schooljaar.
