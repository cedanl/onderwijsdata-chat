---
icon: lucide/messages-square
---

# Voorbeeldvragen

Drie vragen, met wat de app erbij doet en waar je op let. De vragen komen uit de documentatie; hoe de assistent ze beantwoordt, hangt af van het model en de data van dat moment. Er staan daarom geen getallen bij.

## 1. Hoeveel studenten zaten er in het mbo?

**Vraag:** "Hoeveel studenten zaten er in 2022 in het mbo?" Of voor een reeks: "Toon het aantal gediplomeerden in het mbo per jaar als grafiek."

**Wat de app doet:**

1. Zoekt een passende CBS-tabel in de catalogus en haalt hem op.
2. Zet bovenaan het antwoord een regel "Uitgangspunt:" met wat er geteld is.
3. Zet onder het antwoord het blok **Bronnen**, met titel, periode en dataset-ID, en een link naar de bronpagina.
4. Voor mbo-studenten landelijk haalt de app ook DUO op, "Mbo-studenten per instelling" opgeteld over alle instellingen. De regel **Ter controle:** onder het antwoord noemt het getal van die tweede bron en het verschil ([Domeinregels, "Bronparen"](../domeinregels.md#bronparen)).

**Waar je op let:** DUO en CBS tellen hetzelfde met een andere definitie of peildatum. Een verschil is daarom niet meteen een fout. Zie ook de regel "Let op: voorlopig cijfer" als CBS het cijfer nog kan herzien.

## 2. Hoeveel vacatures zijn er in mijn regio?

**Vraag:** een vraag over openstaande vacatures per provincie of bedrijfstak.

**Wat de app doet:** gebruikt CBS-tabel 83599NED: openstaande vacatures per bedrijfstak (SBI-sectie) en regio (Nederland, landsdelen, 12 provincies), per kwartaal, vanaf 2011. De licentie is CC BY 4.0.

**Waar je op let:**

- De cijfers komen een maand na het kwartaal. CBS noemt per kwartaal of het voorlopig is; nu is elk kwartaal vanaf 2022 voorlopig.
- De regio's zijn provincies en landsdelen, geen gemeenten.
- UWV Open Match is een archief van mei 2023. De app gebruikt het in de chat alleen als archief, de actuele vacatures komen van CBS ([Databronnen begrijpen](databronnen.md)).

## 3. Hoe verhoudt mijn instelling zich tot vergelijkbare instellingen?

**Waar:** het dashboard **Mijn instelling** en het dashboard **Landelijk**, waar de omgeving dashboards aanzet.

**Wat de app doet:** vergelijkt je instelling met de andere instellingen van hetzelfde type: een hogeschool met hogescholen, een universiteit met universiteiten, een mbo-instelling met mbo-instellingen. Een peer telt alleen mee als hij ten minste 10% zo groot is als jouw instelling. De groep verbreedt van arbeidsmarktregio naar provincie naar landelijk tot er ten minste drie andere instellingen in zitten.

**Waar je op let:**

- Kleine aantallen publiceert de bron niet (DUO zet 1 tot en met 4 op -1). Een som is dan een ondergrens: de app zegt "ten minste" en een open marker of arcering in de grafiek.
- Een positie landelijk waarin zo'n lege cel meetelt, heet "indicatief".

Meer: [Dashboards](../dashboards.md#de-vergelijkingsgroep-van-mijn-instelling).
