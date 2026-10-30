### Besluit over Plotly in het rapport vastgelegd (#812)
- ADR-008 in `docs/architecture-decisions.md`: ongeveer 1,1 MB gzip Plotly in het rapportframe en 3,4 MB voor een
  download zijn de bewuste prijs voor een rapport dat offline werkt. Het budget van `npm run budget` voor
  `plotly-rapport` blijft de rem; bij klachten op mobiel gaat het besluit weer open. De bundel zelf is niet gewijzigd.
