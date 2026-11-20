### Ongeldige invoer bij opslaan en inloggen geeft 422 in plaats van een serverfout (#1064)
- Een gesprek opslaan zonder titel, tijdstip of berichten, of met een verkeerd type (een tijdstip als tekst, berichten
  die geen lijst van objecten zijn), geeft nu de Nederlandse melding "Ongeldige invoer" (422) in plaats van een 500.
- Hetzelfde geldt voor een werkboek waarvan de berichten of figuren geen lijst zijn, en voor inloggen of het token
  verversen met een gebruikersnaam, wachtwoord of token dat geen tekst is. Een leeg token blijft "Token ontbreekt".
