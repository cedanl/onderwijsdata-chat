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
- `run_analysis` (`tools/analysis.py`) voor wat daar niet mee kan, in een afgeschermde sandbox. Een AST-controle weigert een script met een literal datastructuur van zes of meer getallen (overgetypte data) en een script dat geen data leest (`df` of `store_get`).

### 3. Het antwoord wordt gecontroleerd tegen de data

Na elk chatantwoord draaien deze controles (samengevoegd in `check` in `agent/run.py`). Vinden ze iets, dan trekt de app het antwoord in en krijgt het model **één** correctieronde met wat er niet klopte. Klopt het daarna nog niet, dan blijft het probleem zichtbaar bij het antwoord.

| Controle | Module | Wat het toetst |
|---|---|---|
| Getallen | `agent/grounding.py` | Elk getal van vier of meer cijfers, en elk percentage, staat in de toolresultaten of in eerdere berichten van het gesprek. |
| Selectie | `agent/selectie.py` | Een gevraagd schooljaar of een genoemde instelling zit in de selectie waarop het antwoord rust; een telling of "niet gevonden" rust niet op een afgekapte selectie. |
| Labels | `agent/labels.py` | Opleidingsvorm (VT, DT, DU), dataset-ID en teleenheid (personen of inschrijvingen) kloppen met de bron. |
| Binding | `agent/binding.py` | Een getal staat bij het jaar en de instelling van zijn eigen rij, niet bij een ander jaar uit dezelfde selectie. |

Voor een rapport geldt hetzelfde via `agent/report_checks.py`: een rapport zonder conclusie, reikwijdte of bevinding wordt niet getoond, en tekst die afwezigheid van data claimt naast een gevulde grafiek wordt geweigerd. Voor een dashboard komen KPI-waarden alleen door als ze uit `compute_kpi` komen, en de tekst gaat door dezelfde getalcontrole (`_check_number_sourcing` in `agent/dashboard.py`).

## Wat dit niet dekt

De controles zijn code, geen begrip. Ze vangen een bepaalde klasse fouten en laten andere door:

- **Kleine getallen en jaartallen.** Alleen getallen van vier of meer cijfers, en percentages, worden getoetst.
- **Een getal dat ergens anders in de data staat.** Staat 27.135 in de data, dan is het getal gedekt, ook als het model het bij de verkeerde groep noemt. De bindingscontrole vangt dat alleen als de zin of tabelrij precies één jaar of instelling noemt.
- **Interpretatie.** Een conclusie die niet volgt uit de cijfers, of een causaal verband dat de data niet draagt, is geen getal en wordt niet gecontroleerd.
- **Meerdere teldefinities.** Mengt een beurt personen en inschrijvingen (bijvoorbeeld p01 en p03), dan slaat de teleenheidcontrole bewust over.
- **De bron zelf.** CBS-cijfers kunnen voorlopig zijn en later worden herzien; DUO-cijfers kennen onderdrukte cellen. De app meldt dat, maar controleert niet of de bron klopt.

Een controle die iets mist is dus mogelijk. Daarom is elk antwoord herleidbaar: de redeneerkaart toont per stap de tool en de code, en elke analyse is als Python-snippet te exporteren (zie [Reproduceerbare analyses](reproducibility.md)).

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
