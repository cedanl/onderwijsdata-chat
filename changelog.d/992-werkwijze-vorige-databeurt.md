### Chat: een vervolgvraag over de werkwijze ziet de stappen van de vorige databeurt (#992)
- Na een koppeling (bijvoorbeeld de Studiekeuzedatabase en DUO op `brin` en `croho`) wist het model bij een vervolgvraag
  als "welke sleutels gebruikte je?" niet meer hoe het vorige antwoord tot stand kwam, en antwoordde het "dat kan ik
  niet bevestigen". Het krijgt nu bij elke vervolgbeurt een korte, vaste samenvatting van de laatste eerdere beurt die
  data maakte: de bronnen en datasets en de stappen (toolnaam met filters, kolommen, groepering, sleutels en korrel).
  Ook na heropenen van een opgeslagen gesprek.
- De samenvatting noemt geen waarden uit de data en geen code van een eigen analyse, is hooguit 1.500 tekens en telt
  niet als bron voor getallen: de getalcontrole leest haar niet.
