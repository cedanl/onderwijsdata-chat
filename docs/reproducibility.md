# Reproduceerbare analyses

## Waarom dit belangrijk is

Onderzoeksinstellingen moeten kunnen aantonen HOE zij tot hun bevindingen zijn gekomen. Een getal zonder code is niet controleerbaar. Dit systeem genereert automatisch het Python-script dat onder de motorkap draait — zodat:

- **Auditeurs** je analyse kunnen nazien
- **Collega's** je bevindingen kunnen reproduceren  
- **Toekomstige onderzoekers** exact kunnen zien wat je hebt gedaan
- **Je** niet hoeft te onthouden welke filters je hebt gebruikt

## Hoe het werkt

### 1. Stel een vraag
```
"Hoeveel eerstejaars had het hbo in 2024/25, per type opleiding?"
```

### 2. De app gebruikt tools

Achter de schermen roept de app functies aan, bijvoorbeeld:
- `get_duo_data` — laadt het DUO-bestand met eerstejaars hbo (`p02ho1ejrs`, bestand 0)
- `query_data` — filtert op `STUDIEJAAR` 2024 en telt `AANTAL_EERSTEJAARS_INGESCHREVENEN` op per `TYPE_HOGER_ONDERWIJS`

### 3. De code per stap

Elke tool-aanroep krijgt een Python-snippet (`tools/snippet.py`). In de chat staat die bij de stap, onder "Redenering".
"Exporteer gesprek" zet het hele gesprek in één Markdown-bestand: per antwoord de stappen, elk met zijn snippet als
`python`-codeblok (`frontend/src/conversationExport.js`, #366). Een los `.py`-bestand levert de app niet; je kopieert de
code van de stap die je wilt herhalen.

Dit is de snippet die de app voor de `query_data`-stap hierboven maakt; de commentaarkop over de databewerking en de
pakketversies is weggelaten:

```python
import pandas as pd
from onderwijsbronnen import duo

df = duo.load("p02ho1ejrs", 0)
# DUO-sentinel -1 = onderdrukte cel: DUO publiceert kleine aantallen niet, geen telwaarde. De app sluit ze uit.
# Totalen over een selectie met zulke cellen zijn een ondergrens.
for kolom in df.select_dtypes("number").columns:
    if not any(h in str(kolom).upper() for h in ("MUTATIE", "SALDO", "VERSCHIL", "GROEI", "DELTA")):
        df[kolom] = df[kolom].mask(df[kolom].isin([-1]))
if "STUDIEJAAR" in df.columns:
    df["STUDIEJAAR_LABEL"] = df["STUDIEJAAR"].map(lambda j: f"{j}/{j + 1}")
_kolom = df["STUDIEJAAR"].astype(str)
_exact = _kolom.str.lower().isin(["2024"])
df = df[_exact] if _exact.any() else df[_kolom.str.isdigit() & _kolom.str.lstrip("0").replace("", "0").isin(["2024"])]
group_by = ["TYPE_HOGER_ONDERWIJS"]
for kolom in ["AANTAL_EERSTEJAARS_INGESCHREVENEN"]:
    df[kolom] = pd.to_numeric(df[kolom], errors="coerce")
df = (
    df.groupby(group_by, dropna=False)
    .agg({"AANTAL_EERSTEJAARS_INGESCHREVENEN": lambda s: s.sum(min_count=1)})
    .reset_index()
)
print(df)
```

### 4. Jij voert het uit

Zet de code in een bestand, bijvoorbeeld `analyse.py`, en draai het:
```bash
python analyse.py
```

Resultaat, gedraaid op 1 november 2026 tegen het DUO-bestand met versie van 08-04-2026:
```
  TYPE_HOGER_ONDERWIJS  AANTAL_EERSTEJAARS_INGESCHREVENEN
0     associate degree                             6839.0
1             bachelor                            83013.0
```

Dezelfde getallen gaf `query_data` in de app voor die selectie. Vervangt DUO het bestand, dan kan de uitkomst
verschuiven; de bestandsversie en de md5 laten dat zien (zie "Is het dezelfde data?" hieronder). Beide totalen zijn een
ondergrens: in die selectie vallen onderdrukte cellen (-1).

## Tools die snippets genereren

| Tool | Wat het genereert |
|------|------------------|
| `query_data` | Laadstap van de bron + filters + aggregatie |
| `get_duo_data` | `duo.load()` call + resource |
| `get_cbs_data` | `onderwijsbronnen.cbs.data()` call + filters |
| `get_rio_data` | `onderwijsbronnen.rio.fetch()` call + filters |
| `compute_kpi` | KPI-formule (sum, mean, delta, %) |
| `run_analysis` | Gebruiker's eigen Python-code |
| `create_plot` | Plotly visualisatie |
| `create_choropleth_map` | Geografische kaart |

## Zelfstandig draaien

Een snippet begint altijd met de echte laadstap van zijn bron (bron-ID, resource en filters) via het publieke pakket `onderwijsbronnen` (`onderwijsbronnen.cbs`, `.duo`, `.rio`, `.uwv`, `.roa`; tot #910 de pakketten `onderwijsdata` en `riodata`). Het gebruikt dus nooit iets dat alleen in de app bestaat. Voor DUO-data met een `STUDIEJAAR` voegt de snippet ook `STUDIEJAAR_LABEL` toe (2021 → 2021/2022), zoals de app dat doet.

De laadstap is de aanroep die de app deed, niet de ruwe argumenten van het model (#945): bij DUO de index van het bestand dat de app koos (ook bij een bestandsnaam, een resource-ID, `"4"` of geen resource), de dataset-ID in de spelling van de catalogus (`duo:p01hoinges` en `P01HOINGES` worden `p01hoinges`), bij CBS de `$select` met de dimensies erbij en bij RIO de peildag. Het enige bedoelde verschil is de paginagrens van CBS: de app vraagt hoogstens een pagina rijen, de snippet de hele selectie, met bovenaan een opmerking als de app afkapte. `tests/test_snippet_equivalentie.py` bewaakt dit per tool: het zet de app-tool en de snippet aan het werk op dezelfde invoer, met een opnemer op de laders van `onderwijsbronnen`, en vergelijkt de aanroepen. Een nieuwe tool zonder zo'n geval maakt die test rood.

Boven de code staan twee commentaarregels met de pakketversie waarmee de snippet is gemaakt (`onderwijsbronnen`, en de appversie als die bekend is) en een `pip install` die precies die code ophaalt (#714, #888). Het pakket staat in deze repo (`packages/`) en niet op PyPI, dus de regel installeert het uit een subdirectory van de publieke GitHub-spiegel, op de volledige commit waaruit de app is gebouwd:

```text
# Gemaakt met onderwijsbronnen 0.8.0, app 2.6.0, commit 7d3488aa.
# Dezelfde versies installeren: pip install "onderwijsbronnen @ git+https://github.com/cedanl/onderwijsdata-chat@7d3488aa0da386a087f6363b3f2ffa40049f604b#subdirectory=packages/onderwijsbronnen"
```

Wie de snippet later draait, installeert dus wat de app toen gebruikte, niet wat dan actueel is. De versienummers komen uit het geïnstalleerde pakket en de commit uit het image (`GIT_COMMIT`, hetzelfde als `commit` in `/version`, dat hem per pakket noemt), dus een versiebump verandert de regels vanzelf. Kent de omgeving haar commit niet (lokaal, zonder build-arg), dan zegt de kop "Commit onbekend, dus de nieuwste versie installeren" en laat de regel de revisie weg: geen schijnzekerheid. Een commit die niet op `main` staat (een MR-build) bestaat niet op de spiegel; snippets uit test en playground wel. Snippets van vóór de verhuizing naar de monorepo (#883) noemen `git+https://github.com/cedanl/<pakket>-onderwijsdata@<commit>`; die blijven installeren zolang de oude repo's bestaan (gearchiveerd, niet verwijderd, #889). Snippets van vóór #910 importeren `riodata` of `onderwijsdata` en installeren `#subdirectory=packages/riodata` of `packages/onderwijsdata` op hun eigen commit; die commit heeft die mappen nog, dus ook zij blijven werken. Snippets van vóór #714 hebben geen kop; ze horen bij de oude repo's (`pip install git+https://github.com/cedanl/rio-onderwijsdata.git`, `…/cbs-onderwijsdata.git`). Het huidige pakket `onderwijsbronnen` kent de oude namen niet meer (#914): draai een oude snippet tegen zijn eigen installatie, of vervang de importregel (`from onderwijsbronnen import duo`, `from onderwijsbronnen.cbs import data`). `tests/test_bron_id_vormen.py` toont met `-m live` dat elke opgeslagen importregel tegen zijn eigen installatie draait.

Is de data het resultaat van een eerdere stap (een selectie, een vaste maat of een eigen berekening), dan herhaalt de snippet de stappen van die ouder uit het recept dat de sessie bewaart: eerst de laadstap van de bron, dan de filters, kolommen en aggregaties, of het script van de berekening, gevolgd door `df = pd.DataFrame(result)` als overgang naar de volgende stap. Zo ontstaat `df` binnen één snippet en draait de code opnieuw tegen actuele data, hoeveel rijen het resultaat ook heeft (#624). Het script van een eigen berekening kent alleen het geheugen van de sessie die haar maakte; de database bewaart geen script (#472). Zonder bekend recept of script — na een herstart — blijft alleen een kopie van de rijen over, tot 200 rijen, met een opmerking dat die waarden niet meegroeien met de bron. Bij meer rijen laadt de snippet de hele bron met een `# NB:` dat de uitkomst kan afwijken van wat de app toonde. Is voor een key geen laadstap bekend, dan zegt de snippet dat in een opmerking.

## Is het dezelfde data? Peildag, bestandsversie en hash

Een snippet laadt de bron opnieuw, dus de data kan intussen zijn veranderd. Twee dingen laten dat zien:

- **RIO is een levend register** met tijdreizen via `datumGeldigOp` (#718). De app zet voor elke resource die dat filter kent de dag van de aanroep zelf (dezelfde rijen als zonder filter, gemeten op elf resources), en de snippet herhaalt die dag: `fetch("erkenningen", **{'type': 'BEVOEGD_GEZAG', 'datumGeldigOp': '2026-10-26', …})` geeft dezelfde stand, ook als het register veranderd is. Het manifest en de bronregel noemen de dag ("stand van 26-10-2026"). Een eigen `datumGeldigOp` van de gebruiker blijft staan. Een resource zonder dat filter krijgt in de snippet een opmerking dat de uitkomst kan afwijken.
- **Een inhoudshash van de brontabel** (#715) voor CBS en RIO: het manifest noemt per dataset `inhoudshash`, de logregel `GEPUBLICEERD` noemt hem bij de bronkey en de CSV-export zet hem in de kop, bij een tabel en bij een grafiek of kaart (`tools/exportnoten.py`, #809). Het is de eerste 12 tekens van de sha256 van de CSV-vorm van de geladen tabel (`df.to_csv(index=False)`), te narekenen met `hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()[:12]`. Alleen de brontabel, niet de selecties erop: die volgen uit bron plus stappen. UWV en ROA zijn momentopnamen met een peilmoment.
- **DUO levert een bestandsversie en een md5** (#717). `onderwijsbronnen.duo` (vanaf riodata 0.7.0) neemt uit CKAN over wanneer DUO het bestand verving en zet de md5 van de geladen bytes in `df.attrs["bron"]`. De bronregel en het manifest noemen de versie ("versie van 10-07-2026", de dag in UTC zoals DUO hem geeft). Het manifest (`bronhash`), de logregel `GEPUBLICEERD` en de CSV-kop (tabel, grafiek en kaart) noemen de md5. Die is gelijk aan de `hash` die DUO bij het bestand vermeldt (`resource_show`, gemeten op `p01hoinges`), en je rekent hem na met `md5sum` op een download van het bestand. Een DUO-bestand dat als datastore-dump wordt geleverd (15 van de 288) heeft geen versie: dan staat alleen de md5 er.

Wat dit **niet** zegt: dat het frame ná de verwerking van de app (maskering van -1, `STUDIEJAAR_LABEL`, provincie) byte-voor-byte gelijk is aan wat de snippet maakt. Een controleregel in de snippet is een aparte stap.

## Voor onderzoekers

- Export je chat-sessie na elke analyse: per antwoord staat er een blok "Herkomst" in met model, versies en dataversie (#713); bij een teruggezet gesprek ontbreekt dat
- Voeg snippets toe aan je rapport als "methodologie"
- Laat collega's ze draaien ter verificatie
- Archiveer ze met je onderzoeksgegevens

## Voor auditors

Vraag naar het snippet — de app levert het direct:

> "Toon me de code voor het studentenaantal per opleiding"

Het is de code die de stappen van dat antwoord herhaalt: dezelfde bron, dezelfde filters en dezelfde aggregaties.

## Anti-hallucinatie

Een snippet maakt een getal controleerbaar, maar voorkomt niet dat het model een getal verzint. Daarvoor zijn de
controles na elk antwoord (ADR-001): een getal van vier of meer cijfers of een percentage dat niet in de toolresultaten
staat, levert een correctieronde op. Die controles verkleinen het risico; ze nemen het niet weg. Wat ze niet dekken,
staat in [Anti-hallucinatie architectuur](anti-hallucination-architecture.md#wat-dit-niet-dekt).

Zie [architecture-decisions.md](architecture-decisions.md) voor details.
