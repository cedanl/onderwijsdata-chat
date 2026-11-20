### Docker-build zonder recursieve chown (#1062)
- De runtime-stage geeft de bestanden bij het kopiëren aan `appuser` (`COPY --chown`) in plaats van met `chown -R /app`
  aan het eind. Die stap duurde op de CI-runner 650 s van een build van 13,5 min en zette elk bestand nog eens in een
  eigen laag. Eigenaar en rechten blijven gelijk.
