### Zware frontendtests met een eigen tijdsgrens in CI (#1058)
- Zes tests die op een volle CI-runner over de standaardgrens van 5 s liepen, krijgen een eigen tijdsgrens van 30 s:
  `basiskaart`, `rapportGrafieken` (grenzen van de server), `dashboardRatio` (ratio-KPI), `reportFrame` (de hele
  `it.each`), `verstuurControle` (volle chat) en `dashboardMiniatuur` (gedeelde lading). De globale grens blijft 5 s.
