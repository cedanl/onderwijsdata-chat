### Grafieken voor het rapport sneller omgezet (#1030)
- Het omzetten van de grafieken naar PNG-bestanden voor de server gaat nu met een gewone lus in plaats van een functie
  per byte. Bij grafieken van megabytes is dat een veelvoud sneller (de test op de grenzen: van ~620 ms naar ~40 ms),
  en die test liep op een volle CI-runner niet meer over de grens van 5 s.
