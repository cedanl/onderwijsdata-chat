# Anti-hallucinatie architectuur

## Het probleem

Statistiekbureaus (ONS, Statistics Canada) hebben hun RAG-chatbots stilgezet omdat die getallen gaven die niet te controleren waren. Een taalmodel kan een getal verzinnen, afronden, uit een andere selectie halen of bij het verkeerde jaar zetten. Voor instellingen die op cijfers worden afgerekend is dat niet acceptabel.

Dit systeem **kan niet uitsluiten** dat een model zoiets probeert. Het zorgt ervoor dat de berekening in code gebeurt en dat een antwoord dat niet bij de data past wordt gevangen, in plaats van dat het de gebruiker bereikt. Op deze pagina staat welke lagen dat doen, en wat ze **niet** dekken.

## Drie lagen

### 1. Data blijft in code

De data staat in een store (`tools/store.py`). Het model krijgt na het laden een `data_key`, het schema en een korte preview (`get_cbs_data`, `get_duo_data`, `get_rio_data`). De rijen die het model daarna ziet, vraagt het zelf op met `query_data`; de selectie en de aggregatie gebeuren in code (`tools/query.py`).

Per key bewaart de store ook wat er over de data bekend is (`KeyMeta`): bron, dataset, welke schooljaren en instellingen erin zitten, of de selectie volledig is, en welke laadaanroep hem maakte. De controles in laag 3 gebruiken dat.

### 2. Rekenen gebeurt in code

- `query_data` met `group_by` en `aggregate` voor sommen, gemiddelden, tellingen, minima en maxima.
- `compute_kpi` (`tools/kpi.py`) voor een verschil, percentage, index of de grootste daling of stijging. Het model neemt de teruggegeven waarde over; het rekent niet zelf.
- `run_analysis` (`tools/analysis.py`) voor wat daar niet mee kan. Het script draait in een eigen proces (`tools/sandbox.py`, #62, #410): zelfde interpreter met `-I`, lege omgeving (geen secrets), eigen werkmap, limieten op CPU-tijd en geheugen, geen nieuwe processen en een harde time-out. Een audit hook in dat proces weigert netwerk, schrijven en elk bestand buiten de Python-installatie. Het kindproces krijgt alleen `df` en de tabellen die het script letterlijk met `store_get('key')` opvraagt; de uitkomst komt terug als JSON. Daarvóór weigert een AST-controle (`tools/scriptcontrole.py`) imports, dunders (`__globals__`, ook in strings) en frame-attributen, een literal datastructuur van zes of meer getallen (overgetypte data) en een script dat geen data leest (`df` of `store_get`).
- Een getal dat het script zelf typt, is geen bewijs: `run_analysis` geeft de getallen uit het script (ook `987650 + 4` en `int('987654')`) mee als `scriptconstanten`, en de getalcontrole trekt die van het bewijs van dat resultaat af. `result = 987654 + 0 * len(df)` leest wel data, maar bewijst 987654 niet. Dit is een heuristiek: hij vouwt alleen expressies uit louter getallen, dus een omweg via een variabele (`x = 987650` en later `x + 4`) valt erbuiten. Hij geldt naast de regel dat een script zonder gelezen data geen bron heeft (#201).

### 3. Het antwoord wordt gecontroleerd tegen de data

Na elk chatantwoord draaien deze controles (samengevoegd in `check` in `agent/run.py`). Vinden ze iets, dan trekt de app het antwoord in en krijgt het model **één** correctieronde met wat er niet klopte. Klopt het daarna nog niet, dan blijft het probleem zichtbaar bij het antwoord.

| Controle | Module | Wat het toetst |
|---|---|---|
| Getallen | `agent/grounding.py` | Elk getal van vier of meer cijfers, en elk percentage, staat in de toolresultaten of in eerdere berichten van het gesprek. |
| Selectie | `agent/selectie.py` | Een gevraagd schooljaar of een genoemde instelling zit in de selectie waarop het antwoord rust; een telling of "niet gevonden" rust niet op een afgekapte selectie. |
| Labels | `agent/labels.py` | Opleidingsvorm (VT, DT, DU) en dataset-ID kloppen met de bron. |
| Binding | `agent/binding.py` | Een getal staat bij het jaar en de instelling van zijn eigen rij, niet bij een ander jaar uit dezelfde selectie. |

Voor een rapport geldt hetzelfde via `agent/report_checks.py`: een rapport zonder conclusie, reikwijdte of bevinding wordt niet getoond, en tekst die afwezigheid van data claimt naast een gevulde grafiek wordt geweigerd. Voor een dashboard komen KPI-waarden alleen door als ze uit `compute_kpi` komen, en de tekst gaat door dezelfde getalcontrole (`_check_number_sourcing` in `agent/dashboard.py`).

## Wat dit niet dekt

De controles zijn code, geen begrip. Ze vangen een bepaalde klasse fouten en laten andere door:

- **Kleine getallen en jaartallen.** Alleen getallen van vier of meer cijfers, en percentages, worden getoetst.
- **Een getal dat ergens anders in de data staat.** Staat 27.135 in de data, dan is het getal gedekt, ook als het model het bij de verkeerde groep noemt. De bindingscontrole vangt dat alleen als de zin of tabelrij precies één jaar of instelling noemt.
- **Interpretatie.** Een conclusie die niet volgt uit de cijfers, of een causaal verband dat de data niet draagt, is geen getal en wordt niet gecontroleerd.
- **Teleenheid.** Wat een DUO-bestand telt (personen of inschrijvingen) en wanneer totalen een ondergrens zijn, zet `agent/telling.py` uit de metadata onder het antwoord; het model hoeft het niet te formuleren en wordt er niet op gecontroleerd. Een vergelijking van p01 en p03 toont beide definities.
- **De bron zelf.** CBS-cijfers kunnen voorlopig zijn en later worden herzien; DUO-cijfers kennen onderdrukte cellen. De app meldt dat, maar controleert niet of de bron klopt.

Een controle die iets mist is dus mogelijk. Daarom is elk antwoord herleidbaar: de redeneerkaart toont per stap de tool en de code, en elke analyse is als Python-snippet te exporteren (zie [Reproduceerbare analyses](reproducibility.md)).

Ook een los getal is herleidbaar: een gecontroleerd getal in een dataantwoord opent een citatie met bron, selectie, maat en stap in woorden. De `data_key` (bijv. `duo:p01hoinges:3:a31654ba`) staat daaronder, dichtgeklapt achter "Technische details" (CH-30r, #471). Hij blijft erin omdat hij het enige spoor is van het getal naar zijn toolstap en de data in de store, voor support, audit en reproduceerbaarheid. In de gewone leesregel is hij jargon; weglaten zou dat spoor kosten zonder iets op te leveren.

## Tests

- `tests/test_grounding.py`, `tests/test_selectie.py`, `tests/test_labels.py`, `tests/test_binding.py`: de controles per module.
- `tests/test_report_checks.py`: de rapportcontroles.
- `tests/test_tools_kpi.py`, `tests/test_tools_analysis.py`: de rekentools en de sandbox.
- `tests/test_eval_*.py`: evaluaties met een echt model tegen een ground truth; die draaien niet in CI (ze hebben een API-key nodig).

## Voor auditors

U kunt dit zelf nagaan:

1. **Vraag de Python-snippet** bij een analyse; de redeneerkaart toont hem.
2. **Voer hem uit.** Hij begint met het laden van de bron, met bron-ID en filters.
3. **Vergelijk de getallen** met wat de app rapporteerde.

---

**Zie ook:** [Reproduceerbare analyses](reproducibility.md), [ADR-001](architecture-decisions.md#adr-001-anti-hallucinatie-via-server-side-compute)
