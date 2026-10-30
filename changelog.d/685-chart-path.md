### Het chartpad van de pipeline staat alleen nog in `.gitlab-ci.yml` (#685)
- Een projectvariabele `CHART_PATH` in de GitLab-instellingen ging voor de waarde in `.gitlab-ci.yml`, zodat wie
  Maintainer is het pad kon wijzigen zonder review. `.gitlab-ci.yml` neemt nu de waarde over die de pipeline
  feitelijk gebruikte (`charts/onderwijsdata-chat`); daarna gaat de projectvariabele weg. Er verandert niets aan
  wat de pipeline doet.
