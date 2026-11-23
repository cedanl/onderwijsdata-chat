### "Stop genereren" werkt ook tijdens een lopende tool (#1087)
- Een stop tijdens een toolstap kwam pas bij de gebruiker aan als de tool klaar was: bij een analyse die tot de
  sandboxgrens rekende bleef de knop tot 10 seconden staan en rekende het script door. Nu eindigt de beurt direct als
  gestopt en wordt het rekenproces van de analyse beëindigd. Een stap die nog liep staat daarna als "Gestopt" in de
  redeneerkaart in plaats van te blijven pulseren.
- Tot de server de run beëindigt, heet de knop "Stoppen…". Een bronaanroep kan niet worden afgebroken: die loopt op de
  achtergrond af en zijn uitkomst gaat verloren.
