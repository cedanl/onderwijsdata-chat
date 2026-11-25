# Betrouwbaarheid per release

Per release staat hier hoe vaak EDUdata de vaste vragenset goed beantwoordde. De vragen en hun verwachte antwoorden
staan openbaar in [`tests/e2e/evaluations.json`](https://github.com/cedanl/onderwijsdata-chat/blob/main/tests/e2e/evaluations.json),
de ijkwaarden rechtstreeks uit CBS, DUO en RIO in
[`tests/e2e/ijkwaarden.json`](https://github.com/cedanl/onderwijsdata-chat/blob/main/tests/e2e/ijkwaarden.json)
([Eval framework](kwaliteit-en-veiligheid.md#eval-framework)).

**Wat de score meet en wat niet.** De score meet alleen deze vragenset, gesteld aan de testomgeving van die release,
met de genoemde modellen en het genoemde aantal herhalingen. Een vraag is geslaagd als elke herhaling elke eis haalt:
de juiste tool met de juiste argumenten, de juiste dataset, de verplichte termen en de ijkwaarde exact in het antwoord;
een weigering slaagt alleen zonder verzonnen getal. De score zegt niets over vragen buiten de set, over andere modellen,
over een andere omgeving of over gesprekken van meer beurten. Hij is geen garantie voor één antwoord: controleer een
getal altijd aan de bron die het antwoord noemt. Een slechte score wordt net zo gepubliceerd als een goede.

**Kritiek** zijn de ijk-cases, de weigeringen en het #742-paar (`expected.kritiek`). Een kritieke weigering moet in
elke herhaling slagen, een andere kritieke vraag in een meerderheid ([Promoten](promoten.md), stap 0).

## Overzicht

<!-- betrouwbaarheid:overzicht -->

_Nog geen run gepubliceerd._ De eerste rij komt met de eerstvolgende release.

| Datum | Versie | Commit | Modellen | Herhalingen | Geslaagd per model | Kritieke set | Kritieke weigeringen |
|---|---|---|---|---|---|---|---|

<!-- /betrouwbaarheid:overzicht -->

## Per release

De vragen en ijkwaarden linken naar de spiegel op de commit van de release.

<!-- betrouwbaarheid:releases -->

<!-- /betrouwbaarheid:releases -->

## Zo komt een rij hier

Na de `eval:bronwaarheid`-run van een release ([Promoten](promoten.md), stap 0):

```bash
curl https://<test-url>/version      # versie en volledige commit van de gemeten build
uv run python scripts/betrouwbaarheid.py \
  --slagingspercentage eval_results/slagingspercentage-<datum>.json \
  --versie X.Y.Z --commit <volledige commit>
```

Het script leest ook `kritiek-<datum>.json` uit dezelfde map. Een tweede run van dezelfde release vervangt haar rij;
oudere releases blijven staan. De pagina gaat mee in de release-MR.
