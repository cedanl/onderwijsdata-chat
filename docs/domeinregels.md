# Domeinregels

Sommige kennis over DUO-data staat niet in de data of in de metadata die de chat meekrijgt: −1 is
een onderdrukte cel en geen telwaarde, PROVINCIENAAM in de ho-bestanden is de vestiging en niet de
woonplaats, DT is deeltijd en niet duaal. Die regels staan in één bestand,
[`data/domeinregels.toml`](https://github.com/cedanl/onderwijsdata-chat/blob/main/data/domeinregels.toml).
De tools lezen het en dwingen de regels af in code, niet via een prompttekst.

Een regel toevoegen of wijzigen is een bewerking van dat bestand, geen Python. Elke regel heeft een
bron, en de tests lopen vanzelf over elke regel in het bestand.

## Wat de regels doen

| Regelsoort | Wat de tools ermee doen | Waar je het ziet |
|---|---|---|
| `[sentinel]` | Maken de waarden leeg in elke DUO-tabel die de chat laadt en melden hoeveel cellen dat waren; een totaal over zo'n cel heet een ondergrens. | `get_duo_data`, `query_data`, het Telling-blok, dashboards en code-snippets |
| `[opleidingsvorm]` | Geven de codes een definitie en een woord (VT → Voltijd), alleen bij de genoemde bestanden; de antwoordcontrole toetst "deeltijd (DU)" eraan. | kolomdefinitie in `get_duo_data`, grafieklabels, rapportdefinities |
| `[[kolomcorrectie]]` | Vervangen de riodata-definitie van één kolom in de genoemde bestanden. | `get_duo_data`, `dataset_details`, `search_catalog` |
| `[[herkomst_is_vestiging]]` | Zetten een melding `niet_geschikt_voor` op de genoemde bestanden en herschrijven voorbeeldvragen die naar woonplaats vragen. | `dataset_details`, `search_catalog` |

`[soort]` komt precies één keer voor; `[[soort]]` is een lijst: elk blok met die kop is één regel.

## Velden

Elke regel heeft deze drie velden:

| Veld | Type | Wat erin hoort |
|---|---|---|
| `id` | tekst | Een korte naam, uniek in het bestand, bijv. `p04-diplomajaar`. Foutmeldingen en testnamen gebruiken hem. |
| `bron` | tekst, niet leeg | Waar de regel vandaan komt; zie [Wat hoort in `bron`](#wat-hoort-in-bron). |
| `gecontroleerd` | datum | De dag waarop je de regel tegen de bron hebt nagegaan, **zonder aanhalingstekens**: `2026-10-08`. |

Daarnaast per soort:

| Soort | Veld | Type | Betekenis |
|---|---|---|---|
| `sentinel` | `waarden` | lijst van gehele getallen | Celwaarden die een onderdrukte cel zijn, bijv. `[-1]`. |
| | `betekenis` | tekst | Wat zo'n cel is, zoals de tool-output en snippets het zeggen. |
| | `uitgezonderd_als_kolom_bevat` | lijst van teksten | Een kolom waarvan de naam een van deze delen bevat, blijft ongemaskeerd (daar kan −1 een echte waarde zijn). In hoofdletters. |
| `opleidingsvorm` | `datasets` | lijst van dataset-ID's | De bestanden waarvan de DUO-beschrijving de codes noemt. |
| | `codes` | tabel `CODE = "woord"` | Bijv. `{ VT = "voltijd", DT = "deeltijd", DU = "duaal" }`. Losse woorden, geen leestekens. |
| `kolomcorrectie` | `datasets` | lijst van dataset-ID's | De bestanden waarin de kolom deze betekenis heeft. |
| | `kolom` | tekst | De kolomnaam precies zoals in het bestand, bijv. `"TOTAAL MBO"`. |
| | `definitie` | tekst | De definitie die het model krijgt, in plaats van die van riodata. |
| `herkomst_is_vestiging` | `datasets` | lijst van dataset-ID's | Bestanden waarvan de plaatskolommen de vestiging zijn. |
| | `melding` | tekst | Wat de catalogus als `niet_geschikt_voor` toont. |
| | `voorbeeldvragen` | tabel, optioneel | `"vraag uit de catalogus" = "herschreven vraag"`. |

Alle teksten behalve `bron` staan op één regel tussen `"…"`: wat je ziet is wat het model krijgt. Het
laden weigert daarin een regeleinde (ook `\n` of `"""…"""`), een tab en onzichtbare tekens. `betekenis`
komt namelijk ook in de Python-code van een snippet en in de CSV-export, waar een tweede regel code of een
formule zou worden. Een `bron` mag over meer regels lopen, tussen `"""…"""`. Commentaar begint met `#`.

## Een regel toevoegen

1. Maak een branch en open `data/domeinregels.toml`.
2. Voeg een blok toe, of kopieer een bestaand blok van dezelfde soort en pas het aan:

    ```toml
    [[kolomcorrectie]]
    id = "mbo-instroom-kolomnaam"
    datasets = ["instromende-mbo-studenten"]
    kolom = "KOLOMNAAM ZOALS IN HET BESTAND"
    definitie = "Wat de kolom in deze bestanden betekent, in één regel voor het model."
    bron = """
    DUO, Uitleg kolomnamen bij instromende studenten mbo: "…letterlijke passage…".
    Nagegaan in het bestand van 2025: …
    """
    gecontroleerd = 2026-10-14
    ```

3. Draai de tests, of laat CI ze draaien:

    ```bash
    uv run pytest tests/test_domeinregels.py tests/test_duo_correcties.py tests/retrieval_baseline -q
    ```

4. Een nieuwe of gewijzigde `[[kolomcorrectie]]` of `[[herkomst_is_vestiging]]` verandert de catalogus
   waartegen de retrieval-baseline is gemeten. Dan faalt `test_catalogus_is_de_gemeten_snapshot` tot je
   opnieuw meet (zonder netwerk of LLM):

    ```bash
    uv run python scripts/meet_retrieval.py --schrijf-baseline
    ```

    Controleer daarna de labels in `tests/retrieval_baseline/vragenset.json` en zet het bijgewerkte
    `tests/retrieval_baseline/baseline.json` in dezelfde MR. Weigert het script omdat een kritieke vraag nu
    faalt, dan verandert de regel de zoekresultaten: zie de release-eis in `tests/retrieval_baseline/README.md`.
    `[sentinel]`, `[opleidingsvorm]` en een wijziging alleen in `bron` of `gecontroleerd` raken de catalogus
    niet.

5. Open een MR. Na de merge staat de regel op test met de gewone deploy van `main`; playground krijgt
   hem met de volgende promotie ([Promoten naar playground](promoten.md)). Het bestand zit in de image:
   er is geen manier om het in een draaiende omgeving te wijzigen.

Een nieuwe **soort** regel (bijvoorbeeld hernoemde onderdelen of naamconventies) kan niet alleen in het
bestand: die heeft ook code nodig die de regel afdwingt, en tests. Maak daarvoor een issue.

## Wat hoort in `bron`

Genoeg om de regel na te gaan zonder jou te vragen:

- de **letterlijke passage** uit de DUO-beschrijving of -documentatie, tussen aanhalingstekens, met het
  dataset-ID waar ze staat;
- of een **URL** naar de documentatie (duo.nl, onderwijsdata.duo.nl);
- of een **controle in de data**: welk bestand, wat je hebt geteld of vergeleken, en in welk jaar;
- en het **issuenummer** als een fout antwoord tot de regel leidde (#451).

"Bekend", "zie code" of alleen een issuenummer is te weinig. Pas `gecontroleerd` aan als je de regel
opnieuw nagaat, ook als de tekst niet verandert.

## Welke tests meedraaien

`tests/test_domeinregels.py` leest het echte bestand en draait voor **elke regel** twee tests:

- **contract**: wat de regel noemt bestaat in de gepinde riodata-catalogus, binnen mbo/hbo/wo.
  Een kolomcorrectie: elke dataset staat erin en de kolom staat in `_kolommen` van die dataset. Hernoemt
  DUO een kolom, dan faalt deze test, in plaats van dat de correctie stil wegvalt. Herkomst: elke te
  herschrijven vraag stelt de catalogus nog. Opleidingsvorm: de DUO-beschrijving noemt OPLEIDINGSVORM en
  elke code met zijn woord ("VT voltijd"). Sentinel: een DUO-beschrijving zegt dat cellen "vervangen
  door ‘-1’" zijn. Daarnaast ligt `gecontroleerd` niet in de toekomst.
- **effect**: de regel is zichtbaar in de tools: in `column_definitions` en `dataset_details`
  (kolomcorrectie), `dataset_details` en `search_catalog` (herkomst), de kolomdefinitie en de
  grafieklabels (opleidingsvorm), `mask_sentinels` en de -1-melding (sentinel).

Daarnaast controleert het laden zelf het schema; zie hieronder. `test_duo_correcties.py` loopt ook over
de kolomcorrecties; `test_duo_kolomdefinities.py` en `test_sentinel_masking.py` testen het gedrag van de
huidige regels.

CI draait de hele map `tests/`. Twee onderdelen daarvan raken een regel zonder hem bij naam te noemen:

- `tests/retrieval_baseline`: de catalogusdigest omvat de kolomcorrecties en de herkomstregels; zie stap 4
  van [Een regel toevoegen](#een-regel-toevoegen).
- `tests/test_catalog_gouden_set.py`: `search_catalog` zoekt ook in de voorbeeldvragen, dus een
  herschreven vraag kan de volgorde van de treffers verschuiven.

De tests tonen dat een regel toepasbaar is, niet dat hij klopt. Dat laatste is de bron en de review
van de MR.

## Als het bestand niet klopt

Het laden faalt dan, met een melding die de regel noemt:

```text
domeinregels.toml: regel 'p04-diplomajaar' (kolomcorrectie): 'bron' ontbreekt
domeinregels.toml: regel 'p04-diplomajaar' (kolomcorrectie): onbekende sleutel 'kollom' (typefout?); toegestaan: …
domeinregels.toml: regel 'p04-diplomajaar' (kolomcorrectie): 'gecontroleerd' moet een datum zijn zonder aanhalingstekens (2026-10-08), niet tekst
domeinregels.toml: regel 'duo-onderdrukte-cel' (sentinel): 'betekenis' moet op één regel staan, zonder regeleinde of onzichtbaar teken (U+000A)
domeinregels.toml: onbekende regelsoort 'kolomcorectie'; bekend: 'sentinel', 'opleidingsvorm', 'kolomcorrectie', 'herkomst_is_vestiging'
```

Geweigerd worden: een ontbrekend of leeg veld (`bron` en `id` inbegrepen), een dubbel `id`, een
onbekende sleutel, een verkeerd type, een lege lijst of tabel, een regeleinde, tab of onzichtbaar teken
in een andere tekst dan `bron`, een onbekende regelsoort, een ontbrekende `[sentinel]` of
`[opleidingsvorm]`, twee correcties op dezelfde kolom van een dataset en een dataset in twee
herkomstregels. Er is geen terugval op lege regels of standaardwaarden: de tests falen in CI, en
een image met zo'n bestand start niet.
