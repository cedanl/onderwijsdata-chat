### Privacy- en feedbackteksten noemen de ingestelde termijnen (#835)
- De privacy-informatie en de feedbackdialogen noemden 90 en 365 dagen, 8 en 24 uur als vaste tekst, terwijl de
  backend die termijnen uit `BEWAARTERMIJN_GESPREKKEN_DAGEN`, `BEWAARTERMIJN_RAPPORTEN_DAGEN`, `SESSION_TTL_HOURS` en
  `SESSION_MAX_HOURS` leest. `/api/config` geeft ze nu mee en de teksten vullen ze in; met de standaardinstelling
  verandert er niets aan wat er staat.
- Weigert de opschoning een bewaartermijn (geen geheel getal of korter dan 7 dagen; dan verwijdert zij niets), dan
  geeft `/api/config` geen getal en blijft de standaardtekst staan.
