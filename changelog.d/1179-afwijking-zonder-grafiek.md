### Rapport: "Afwijking van je vraag" toetst de periode ook zonder grafiek (#1179)
- Een rapport zonder grafiek meldde nooit dat de data later begint dan gevraagd ("vanaf 2010", terwijl de bron in 2011/12
  begint), omdat de periode alleen tegen de tijdas van de grafieken werd getoetst. Heeft het rapport geen grafiek met een
  tijdas, dan toetst code de gevraagde periode nu tegen de schooljaren van de data die het rapport las, en zegt de regel
  dat: "Gevraagd was vanaf 2010; de data loopt van 2011/12 t/m 2024/25." Met een grafiek blijft de regel zoals hij was
  ("de grafieken tonen …"). Kent de store de schooljaren niet, dan komt er geen regel.
