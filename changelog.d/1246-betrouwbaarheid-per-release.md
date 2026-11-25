### Docs: de betrouwbaarheid per release staat openbaar op de docs-site (#1246)
- Nieuwe pagina "Betrouwbaarheid per release" (`docs/betrouwbaarheid.md`) onder "Kwaliteit & veiligheid": per release de
  datum, versie, commit, modellen, herhalingen, het slagingspercentage per model, de kritieke set en de kritieke
  weigeringen, en per vraag geslaagd of niet met een link naar de vraag en de ijkwaarde. Een slechte score gaat er ook
  op; de pagina zegt wat de score wel en niet meet.
- `scripts/betrouwbaarheid.py` zet de uitslag van de `eval:bronwaarheid`-run erop; de stap staat in
  `docs/promoten.md`. Er staat nog geen run op: de eerste rij komt met de eerstvolgende release.
