### Productie draait bewust één pod; een uitrol zegt "De app wordt bijgewerkt" (#677)
- Besluit 09-11: de eerste productie draait één pod (ADR-011). De chart heeft geen HPA-knop meer
  (`autoscaling.enabled` liet zonder HPA-template alleen `replicas` weg); `tests/test_manifests.py` toetst per omgeving
  de gerenderde chart: één replica, geen HPA, geen PDB. Opschalen is de vervolgepic #984.
- Stoppen: de pod wacht eerst 5 s (`preStop`), zodat Traefik hem loslaat voordat uvicorn stopt met luisteren; daarna
  krijgen lopende HTTP-verzoeken 45 s, binnen de termijn van 60 s.
- Sluit de server een chat voor een uitrol of herstart (WebSocket-code 1012), dan zegt de voettekst "De app wordt
  bijgewerkt. De verbinding komt vanzelf terug." en blijft de app tot 12 minuten opnieuw verbinden. Eerder gaf hij na
  ± 15 s op met "Geen verbinding.", terwijl een uitrol op test minuten duurt.
- `docs/operatie.md`, `docs/deployment.md` en `manifests/README.md` zeggen wat één pod betekent (elke uitrol een
  onderbreking, limieten per proces); `docs/operatie.md` beschrijft de beschikbaarheid: best effort, geen vaste
  onderhoudsvensters, en wat gebruikers bij een uitrol of storing zien.
