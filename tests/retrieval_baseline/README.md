# Retrieval-baseline voor search_catalog (#359)

Hoe goed vindt `search_catalog` de juiste dataset? Deze meting antwoordt zonder LLM en zonder
netwerk, op een vaste vragenset, per sector. Zonder baseline is elke zoekwijziging (`_score`,
`_SYNONYMS`, later hybride retrieval met BM25 en embeddings) een gok.

Aanvulling op de gouden set (`tests/test_catalog_gouden_set.py`, #33: rangregressies per query),
de modelroute-evals (#190, `tests/e2e`) en de weigervragen (#36). Overlap in queries mag.

## Bestanden

| Bestand | Inhoud |
|---|---|
| `vragenset.json` | de vaste vragen met hun labels |
| `baseline.json` | catalogussnapshot, gemeten baseline per cel en de kritieke vragen die bij de baseline al falen |
| `meting.py` | pure rekenfuncties: rang, recall@5, MRR en hun 95%-intervallen |
| `harnas.py` | draait `search_catalog` zonder netwerk en zonder instellingsregister |
| `rapport.py` | de tabel per sector × reeks en de inhoud van `baseline.json` |
| `test_meting.py`, `test_retrieval_baseline.py` | pytest: rekenwerk, vragenset, snapshot, release-eis, rapport |
| `scripts/meet_retrieval.py` | het rapport op de commandoregel |

## Vragenset

Elke vraag heeft:

- `id`: uniek, bijvoorbeeld `mbo-03`.
- `sector`: `mbo`, `hbo` of `wo`; ten hoogste 8 vragen `buiten_profiel` (po/vo), op een eigen rij.
- `reeks`: `ontwikkel` of `test`.
- `vraag`: de vraag zoals een gebruiker hem stelt.
- `zoekinput`: vaste trefwoorden, zoals het model ze volgens de toolbeschrijving stuurt (2 tot 4
  trefwoorden). Optioneel `source` (standaard `both`) en `geo_niveau`.
- `geaccepteerd`: de datasets die de vraag op datasetniveau kunnen beantwoorden; één is genoeg.
  Leeg betekent: onbeantwoordbaar met deze catalogus.
- `beantwoordbaar`: gelijk aan "`geaccepteerd` is niet leeg".
- `verboden`: datasets die niet in de top 5 mogen staan, omdat ze het model naar een fout antwoord
  leiden: een vo-bestand bij een mbo-vraag (`voprognoses`), een ho-bestand met de vestigingsgemeente
  bij een vraag over woonplaats (`niet_geschikt_voor`), inschrijvingen (`p03hoinschr`) bij een vraag
  over unieke studenten, een bestand met alleen documentatie (een DUO-changelog), of een CBS-tabel
  over alle onderwijssoorten zonder sectorselectie. Een verboden ID buiten het profiel kan nu niet in
  de top 5 komen; zo'n vraag bewaakt de scopegrens (#355).
- `kritiek`: de vraag valt onder de release-eis hieronder. Een kritieke vraag heeft altijd `verboden`.
- `toelichting`: het bewijs uit de catalogus voor de labels.

Regels:

1. Labels komen uit de catalogusmetadata: `bron`, `beschrijving`, `samenvatting`, `tags`,
   `_kolommen`, `_dimensies`, `niet_geschikt_voor` en `scopeprofiel.TOEGELATEN`. Nooit uit de huidige
   top 5. Een vraag die de zoekfunctie mist, blijft erin; de `toelichting` zegt waarom hij past.
2. Geen personen en geen persoonsgegevens: vragen noemen alleen organisaties. Een test zoekt naar
   e-mailadressen, telefoonnummers en BSN-achtige getallen.
3. `ontwikkel` mag je bekijken als je de zoekfunctie verbetert; `test` niet. Tune nooit op `test`,
   verplaats nooit een vraag van de ene reeks naar de andere, en wijzig geen label van een
   testvraag na een meting zonder dat in de MR te verantwoorden. Dit is een afspraak, geen technisch
   slot: de git-historie maakt een overtreding zichtbaar. Een nieuwe vraag krijgt zijn reeks bij het
   toevoegen, vóór hij gemeten is.

## Maten

- **Rang**: de plaats (1 is de eerste) van een geaccepteerde dataset in de eerste 15 treffers
  (`top_n=15`), op datasetniveau. Niet in de eerste 15: geen rang.
- **recall@5**: het aandeel beantwoordbare vragen met ten minste één geaccepteerde dataset in de
  top 5 (de hit-rate-vorm).
- **MRR**: het gemiddelde over de beantwoordbare vragen van 1/rang van de eerste geaccepteerde
  dataset; 0 als er geen in de eerste 15 staat.
- **Onzekerheid**: een Wilson-95%-interval voor recall@5 en een bootstrap-95%-interval voor MRR
  (2000 trekkingen met teruglegging, vaste seed 359, percentielmethode). Een cel met minder dan 10
  beantwoordbare vragen heet **indicatief**.
- **Onbeantwoordbaar geslaagd**: bij een vraag zonder geaccepteerde dataset geeft `search_catalog`
  geen kandidaat (`no_match`, of de geo-melding zonder treffers). Informatief: de lexicale zoekfunctie
  geeft al treffers zodra één term raakt, dus dit getal zegt hoe vaak het model zelf moet weigeren.
- **Kritiek geslaagd**: geen `verboden` ID in de top 5.
- **Vraag als invoer**: recall@5 en MRR met `vraag` in plaats van `zoekinput`. Het verschil is het gat
  in queryvorming. Informatief.
- **Latentie**: p50 en p95 van één `search_catalog`-aanroep met de `zoekinput`. Hangt af van de
  machine en staat daarom niet in de baseline.

Een resultaat dat geen JSON-lijst is (`no_match`, de geo-melding) telt als lege ranglijst. Het ID van
een treffer komt van `scopeprofiel.dataset_id`; de ROA-records (`ais2028`, `ais2030`) verliezen
`_roa_id` in de zoekuitvoer, en daarvoor valt de meting terug op de unieke `bron`-titel.

De meting zet `instelling.noemt_instelling` en `instelling.genoemde_namen` uit (die bouwen het
instellingsregister uit DUO-downloads) en laat elke socketverbinding falen. Instellingsroutering
(#334) valt dus buiten deze meting.

## Release-eis

Vooraf vastgelegd op 9 oktober 2026, vóór de eerste meting.

1. Een kritieke vraag faalt als een `verboden` ID in de top 5 staat van zijn `zoekinput`. Dat geldt
   voor `ontwikkel` en `test`.
2. Kritieke vragen die bij de baseline al falen, staan in `baseline.json` onder `kritiek_falend` en
   draaien als strict xfail, net als de bekende missers in de gouden set. Lost een wijziging er een op,
   dan faalt die test: meet opnieuw, zodat de vraag uit de lijst gaat.
3. Een kritieke vraag die bij de baseline slaagde en nu faalt, laat pytest falen met het vraag-ID, het
   verboden ID en zijn rang. Dat blokkeert de release.
4. recall@5 en MRR zijn geen poort. Het rapport geeft ze met het verschil ten opzichte van de
   baseline. Bij 5 tot 25 vragen per cel zijn de intervallen te breed om een verschil hard te maken
   (Wilson ±0,3 bij n = 6).
5. `--schrijf-baseline` weigert een nieuwe baseline waarin een kritieke vraag faalt die in de oude
   baseline slaagde, tenzij `--accepteer-kritiek` erbij staat. Zo'n MR verantwoordt de regressie.

## Catalogussnapshot

`baseline.json` legt vast tegen welke catalogus gemeten is: `catalogus_digest()`, de commits uit
`catalogusversie()`, `dataset_counts()`, de gesorteerde lijst doorzoekbare dataset-ID's en de
meetdatum. Daarnaast de metingen per sector × reeks en `kritiek_falend`.

Wijkt de digest af, dan faalt `test_catalogus_is_de_gemeten_snapshot`. Dat gebeurt na een
catalogusbump of een wijziging aan `tools/duo_correcties.py` of `tools/scopeprofiel.py`, en is zo
bedoeld: meet opnieuw, controleer of de labels nog kloppen (een vervallen ID laat de validatie van de
vragenset falen) en verantwoord de verschillen in de MR.

## Draaien

```bash
UV_PYTHON=3.14 uv run python scripts/meet_retrieval.py                     # rapport, details van ontwikkel
UV_PYTHON=3.14 uv run python scripts/meet_retrieval.py --toon-test         # ook details van test
UV_PYTHON=3.14 uv run python scripts/meet_retrieval.py --schrijf-baseline  # opnieuw meten en vastleggen
UV_PYTHON=3.14 uv run pytest tests/retrieval_baseline -q
```

## Buiten deze meting

Rangschikking binnen een dataset (resources), instellingsroutering (#334), het model zelf (#190) en
hybride retrieval. Dat laatste is een vervolg, alleen als deze baseline lexicale gaten laat zien, en
binnen een budget voor latentie en geheugen.
