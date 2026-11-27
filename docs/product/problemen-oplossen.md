---
icon: lucide/life-buoy
---

# Problemen oplossen

| Wat je ziet | Wat het betekent | Wat je doet |
|---|---|---|
| "Je sessie is verlopen. Log opnieuw in." | Een sessie duurt 8 uur en wordt bij gebruik verlengd tot 24 uur na het inloggen. | Log opnieuw in. |
| "Te veel inlogpogingen. Probeer het over N seconden opnieuw." | Een limiet op inlogpogingen. | Wacht het aantal seconden dat de melding noemt. |
| "Te veel verzoeken in korte tijd. Probeer het over N seconden opnieuw." | Een limiet op het aantal vragen per tijd. | Wacht het aantal seconden dat de melding noemt. |
| Een foutmelding in het antwoord, of een antwoord dat afbreekt | De vraag mislukte, bijvoorbeeld door het maximale aantal stappen of een limiet van het model. | Kies **Opnieuw**. Met **Geavanceerd** staat er ook "Opnieuw met" een ander model, en dat lukt vaak wel. |
| Een melding boven de pagina over een bron | Een bron antwoordt niet. De app meet dat standaard elke 120 seconden. | Wacht en probeer het later opnieuw. Zie [Actualiteit van de bronnen](databronnen.md#hoe-actueel-zijn-de-cijfers). |
| "Eerste versie van dit antwoord is aangepast na controle" | De controle vond een fout in het eerste antwoord. | Lees het aangepaste antwoord en de regel "Let op". |
| "Zinnen met een getal dat niet in de opgehaalde data staat, zijn weggelaten." | De controle haalde een zin of tabelrij weg. | Vraag opnieuw als je de weggelaten gegevens nodig hebt. |
| "Deze cel is door de bron onderdrukt; terugrekenen geven we niet." | De bron publiceert kleine aantallen niet. | Dit is bedoeld en geen fout. |
| Een getal met "ten minste" of "≥" | Een som met een onderdrukte cel is een ondergrens. | Lees het als minimum. |
| Een download mislukt | De CSV-download lukte niet. | Kies "Vraag opnieuw stellen" (met **Geavanceerd**). |
| Een gesprek of rapport staat na het verwijderen weer in de lijst | De server kon de verwijdering niet verwerken. | Kies "Opnieuw proberen" in de melding. |
| De knoppen "Exporteer al mijn gegevens" en "Verwijder al mijn gegevens" ontbreken | Zonder eigen login ben je de gedeelde gebruiker `gast`. | Log in met een eigen account. |
| Het antwoord wijkt af van je eigen cijfers | DUO en CBS tellen hetzelfde met een andere definitie of peildatum, en een bestand telt soms personen en soms inschrijvingen. | Lees de regels onder het antwoord, en bij een vaste maat de regel "Ter controle". |

Lost dit het niet op, of klopt de documentatie niet? [Open een issue](https://github.com/cedanl/onderwijsdata-chat/issues). Beheerders vinden meer onder [Operatie & runbook](../operatie.md).
