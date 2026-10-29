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
"Hoeveel eerstejaars hadden HBO opleidingen in 2023?"
```

### 2. De app gebruikt tools

Achter de schermen roept de app functies aan:
- `get_duo_data()` — Laadt DUO dataset
- `query_data()` — Filtert op OPLEIDINGSVORM="VT", JAAR=2023
- `compute_kpi()` — Telt totaal eerstejaars

### 3. Exporteer als code

Elke tool-aanroep genereert Python-snippet. Het app verzamelt ze in één reproduceerbaar script:

```python
# Laad DUO eerstejaars HBO 2023
from riodata import duo
import pandas as pd

# Dataset laden
df = duo.load("p02ho1ejrs", "Eerstejaarsingeschrevenen hoger onderwijs")

# Filter op HBO (ONDERDEEL="HBO")
df = df[df["ONDERDEEL"] == "HBO"]

# Filter op 2023 (STUDIEJAAR=2023)
df = df[df["STUDIEJAAR"] == 2023]

# Aggregatie: som eerstejaars
totaal = df["AANTAL_EERSTEJAARS_INGESCHREVENEN"].sum()
print(f"HBO eerstejaars 2023: {totaal}")
```

### 4. Jij voert het uit

Run het script zelf:
```bash
python analyse.py
```

Resultaat:
```
HBO eerstejaars 2023: 42583
```

Dit getal matcht precies wat de app rapporteerde. Geen gissing, geen "zwarte doos" — pure reproducibiliteit.

## Tools die snippets genereren

| Tool | Wat het genereert |
|------|------------------|
| `query_data` | Laadstap van de bron + filters + aggregatie |
| `get_duo_data` | `duo.load()` call + resource |
| `get_cbs_data` | `onderwijsdata.data()` call + filters |
| `get_rio_data` | `riodata.fetch()` call + filters |
| `compute_kpi` | KPI-formule (sum, mean, delta, %) |
| `run_analysis` | Gebruiker's eigen Python-code |
| `create_plot` | Plotly visualisatie |
| `create_choropleth_map` | Geografische kaart |

## Zelfstandig draaien

Een snippet begint altijd met de echte laadstap van zijn bron (bron-ID, resource en filters) via de publieke pakketten `onderwijsdata` en `riodata`. Het gebruikt dus nooit iets dat alleen in de app bestaat. Voor DUO-data met een `STUDIEJAAR` voegt de snippet ook `STUDIEJAAR_LABEL` toe (2021 → 2021/2022), zoals de app dat doet.

Boven de code staan twee commentaarregels met de pakketversies waarmee de snippet is gemaakt (`onderwijsdata`, `riodata`, en de appversie als die bekend is) en een `pip install` met dezelfde versies, bij een git-installatie op de exacte commit (#714). Wie de snippet later draait, installeert dus wat de app toen gebruikte, niet wat dan actueel is. De versies komen uit het geïnstalleerde pakket, dus een versiebump verandert de regels vanzelf.

Is de data het resultaat van een eerdere stap (een selectie, een vaste maat of een eigen berekening), dan herhaalt de snippet de stappen van die ouder uit het recept dat de sessie bewaart: eerst de laadstap van de bron, dan de filters, kolommen en aggregaties, of het script van de berekening, gevolgd door `df = pd.DataFrame(result)` als overgang naar de volgende stap. Zo ontstaat `df` binnen één snippet en draait de code opnieuw tegen actuele data, hoeveel rijen het resultaat ook heeft (#624). Het script van een eigen berekening kent alleen het geheugen van de sessie die haar maakte; de database bewaart geen script (#472). Zonder bekend recept of script — na een herstart — blijft alleen een kopie van de rijen over, tot 200 rijen, met een opmerking dat die waarden niet meegroeien met de bron. Bij meer rijen laadt de snippet de hele bron met een `# NB:` dat de uitkomst kan afwijken van wat de app toonde. Is voor een key geen laadstap bekend, dan zegt de snippet dat in een opmerking.

## Is het dezelfde data? Peildag, bestandsversie en hash

Een snippet laadt de bron opnieuw, dus de data kan intussen zijn veranderd. Twee dingen laten dat zien:

- **RIO is een levend register** met tijdreizen via `datumGeldigOp` (#718). De app zet voor elke resource die dat filter kent de dag van de aanroep zelf (dezelfde rijen als zonder filter, gemeten op elf resources), en de snippet herhaalt die dag: `fetch("erkenningen", **{'type': 'BEVOEGD_GEZAG', 'datumGeldigOp': '2026-10-26', …})` geeft dezelfde stand, ook als het register veranderd is. Het manifest en de bronregel noemen de dag ("stand van 26-10-2026"). Een eigen `datumGeldigOp` van de gebruiker blijft staan. Een resource zonder dat filter krijgt in de snippet een opmerking dat de uitkomst kan afwijken.
- **Een inhoudshash van de brontabel** (#715) voor CBS en RIO: het manifest noemt per dataset `inhoudshash`, de logregel `GEPUBLICEERD` noemt hem bij de bronkey en de CSV-export zet hem in de kop, bij een tabel en bij een grafiek of kaart (`tools/exportnoten.py`, #809). Het is de eerste 12 tekens van de sha256 van de CSV-vorm van de geladen tabel (`df.to_csv(index=False)`), te narekenen met `hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()[:12]`. Alleen de brontabel, niet de selecties erop: die volgen uit bron plus stappen. UWV en ROA zijn momentopnamen met een peilmoment.
- **DUO levert een bestandsversie en een md5** (#717). `riodata` (vanaf 0.7.0) neemt uit CKAN over wanneer DUO het bestand verving en zet de md5 van de geladen bytes in `df.attrs["bron"]`. De bronregel en het manifest noemen de versie ("versie van 10-07-2026", de dag in UTC zoals DUO hem geeft). Het manifest (`bronhash`), de logregel `GEPUBLICEERD` en de CSV-kop (tabel, grafiek en kaart) noemen de md5. Die is gelijk aan de `hash` die DUO bij het bestand vermeldt (`resource_show`, gemeten op `p01hoinges`), en je rekent hem na met `md5sum` op een download van het bestand. Een DUO-bestand dat als datastore-dump wordt geleverd (15 van de 288) heeft geen versie: dan staat alleen de md5 er.

Wat dit **niet** zegt: dat het frame ná de verwerking van de app (maskering van -1, `STUDIEJAAR_LABEL`, provincie) byte-voor-byte gelijk is aan wat de snippet maakt. Een controleregel in de snippet is een aparte stap.

## Voor onderzoekers

- Export je chat-sessie na elke analyse: per antwoord staat er een blok "Herkomst" in met model, versies en dataversie (#713); bij een teruggezet gesprek ontbreekt dat
- Voeg snippets toe aan je rapport als "methodologie"
- Laat collega's ze draaien ter verificatie
- Archiveer ze met je onderzoeksgegevens

## Voor auditors

Vraag naar het snippet — de app levert het direct:

> "Toon me de code voor het studentenaantal per opleiding"

Geen ambiguïteit, geen achteraf geknutsel. Het is het óf-of-code dat je gebruiker daadwerkelijk hebt gerund.

## Anti-hallucinatie control

Omdat snippets altijd data-tools gebruiken, kan het model nooit een getal verzinnen:

```
❌ NIET MOGELIJK:
    "Het aantal studenten was 50.000"     ← Getal niet uit tool
    
✓ ALTIJD UIT DATA:
    df.groupby("JAAR")["AANTAL"].sum()    ← Uit data
    compute_kpi(metric="sum", ...)        ← Uit tool
```

Zie [architecture-decisions.md](architecture-decisions.md) voor details.
