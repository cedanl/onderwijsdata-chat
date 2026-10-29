### Een antwoord met grafiek schuift op een telefoon niet meer terwijl het stroomt (#808)
- Kwam de grafiek binnen terwijl de tekst nog moest komen, dan gold het antwoord al als klaar: de knop "Download data
  als CSV" stond in een bubbel zonder tekst. Die bubbel sprong omhoog toen de redenering bij de eerste regel inklapte,
  en daarna schoof de knop bij elke gestreamde regel omlaag. Op 390 px was dat een CLS van 0,073–0,105 per antwoord
  (staafgrafiek en kaart, licht en donker), nu 0,0007. Een grafiekbericht telt niet meer als volgende ronde
  (`roundSettled`), dus de knop en de blokken komen pas als het antwoord af is, in één keer onder de tekst. Dezelfde
  oorzaak als het etiket "Antwoord van …" in #661.
