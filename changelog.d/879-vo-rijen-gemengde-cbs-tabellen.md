### Vo-rijen van de gemengde CBS-tabellen bij een doorstroomvraag (#879)
- Een doorstroomvraag die zelf het vo noemt ("Hoeveel vo-leerlingen worden voortijdig schoolverlater en hoeveel
  daarvan in het mbo?") laadt nu ook de vo- en vavo-rijen van de VSV-tabellen (`85368NED`, `85367NED`) en de
  woonregiotabellen (`85701NED`, `85702NED`). De totalen over vo en mbo samen en de po- en (v)so-rijen blijven weg.
- Een mbo-vraag, een hbo-vraag zonder vo-niveau en een aanroep buiten de chat laden zoals voorheen alleen de
  mbo/hbo/wo-rijen.
- De bronregel zegt welk deel geladen is: "…, alleen mbo en vo (vo-context voor vervolgonderwijs)", ook in de Bronnen,
  onder een rapportgrafiek, in de kop van een CSV-export en in de snippet. Dat staat per lading vast: een eerdere
  bronregel verandert niet door een latere beurt, en herladen geeft dezelfde rijen terug.
