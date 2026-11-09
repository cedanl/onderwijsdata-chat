### De duimpjes onder een antwoord zijn weg (#983)
- Onder een chatantwoord staan geen 👍/👎 meer, en ook het veld "Wat klopt er niet?" na een 👎 is weg. De rij onder het
  antwoord eindigt bij "Antwoord van <model>", zonder lege ruimte. De feedbackvragen op rapporten en dashboards en de
  link Feedback blijven.
- Het eindpunt `/api/answer-feedback` (GET en POST), de trace per antwoord en het overzicht voor het team
  (`scripts/antwoordfeedback.py`) zijn verwijderd.
- Wat er al aan feedback per antwoord stond, blijft tot de nachtelijke opschoning; "Exporteer al mijn gegevens" en
  "Verwijder al mijn gegevens" nemen het mee, en een verwijderd gesprek koppelt het los zoals voorheen. De
  privacytekst zegt dat duimpjes geven niet meer kan. Het bewijs per antwoord (ADR-009) blijft ongewijzigd.
