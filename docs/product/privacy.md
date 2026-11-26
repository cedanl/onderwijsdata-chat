---
icon: lucide/lock
---

# Privacy in gewone taal

Dit is een samenvatting van [Privacy-informatie](../privacy.md). Die pagina is de volledige tekst en geldt als er verschil is. Het gaat om de werking van de demoversie; de formele privacyverklaring is nog niet vastgesteld en er zijn open punten (zie onderaan de volledige tekst).

## Wat naar de AI-dienst gaat

- Je vraag, de eerdere berichten van het gesprek, je instelling en functie uit je profiel en de opgehaalde data gaan naar een externe AI-dienst die het antwoord formuleert. Welke dienst en welk model dat is, staat onder het invoerveld.
- De bronnen (CBS, DUO, RIO en andere) krijgen alleen de opvraag te zien: welke tabel, welke selectie. Niets over jou.
- **Voer geen persoonsgegevens in.** De app waarschuwt bij een BSN, e-mailadres of telefoonnummer, maar blokkeert en maskeert niet, en een naam herkent ze niet. Verstuur je ze toch, dan gaan ze naar de AI-dienst en blijven ze in het gesprek staan tot je het gesprek verwijdert.
- Kleine aantallen blijven onderdrukt. De app rekent ze niet terug uit een totaal.

## Wat de server bewaart

| Wat | Hoe lang |
|---|---|
| Gesprekken | 90 dagen na het laatste bericht |
| Rapporten en dashboards | 365 dagen na het laatst opslaan of openen |
| Feedback | 90 dagen |
| Gegevens uit je SRAM-account voor de kop van de app (alleen met SRAM) | tot 24 uur na het inloggen |

Alles gaat eerder weg als je het zelf verwijdert. De volledige tabel, met ook de tellers en het bewijs per antwoord, staat in [Privacy-informatie](../privacy.md#wat-de-server-bewaart). De serverlogs en de back-ups van de beheerder vallen buiten de opschoning.

## Wat in je browser staat

Een kopie van je gesprekken, rapporten en profiel, en het sessietoken. Uitloggen wist dat. De app gebruikt geen cookies behalve kort tijdens het inloggen met SRAM, en geen analytics.

## Wat je zelf kunt doen

- Een gesprek of rapport verwijderen.
- Een gesprek of rapport exporteren.
- In Instellingen: **Exporteer al mijn gegevens** (een JSON-bestand) en **Verwijder al mijn gegevens**. Verwijderen kan niet ongedaan worden gemaakt. Zonder eigen login kan beide niet.

## Wie is verantwoordelijk

De deelnemende instelling is de verwerkingsverantwoordelijke. Met een privacyvraag ga je naar de privacycontactpersoon of de functionaris gegevensbescherming van die instelling. Het projectteam van CEDA beantwoordt alleen vragen over de demo zelf.
