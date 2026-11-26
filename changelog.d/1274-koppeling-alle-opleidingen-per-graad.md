### Chat: "alle opleidingen" van een instelling per graad, met score en reden, in code (#1274)
- Koppelt `koppel_data` de Studiekeuzedatabase en DUO op brin en CROHO, dan staan ook de gekoppelde opleidingen per
  graad geteld in `gekoppeld_per_graad` (bij HU 54 bachelor en 15 associate degree), elk met het aantal met een
  NSE-score en het aantal onzeker. Een opleiding met 28 respondenten (CROHO 80166) telt mee, met haar label.
- `niet_gekoppeld_per_graad` telt per graad ook het aantal met een NSE-score (bij HU 29 masters, waarvan 27 met score).
  Let op: elke graad is nu een object (`rijen`, `met_score`, `onzeker`) in plaats van een getal.
- De DUO-opleidingen zonder SKDB-rij staan in `alleen_duo`, met een vaste reden (bij HU CROHO 80065). Samen tellen de
  delen op tot alle rijen van de koppeling.
- Bij een vraag naar alle opleidingen zegt de toelichting het model één tabel per graad te tonen, de rijen zonder match
  met hun reden, onzekere rijen met label, en de graad niet ongevraagd te vernauwen.
