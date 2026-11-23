### Verwijder al mijn gegevens: ook de lijst van recent bekeken gesprekken in de browser gaat weg (#1115)
- De verwijderdialoog zegt "Ook de kopie in deze browser gaat weg", maar `openEDUdata_recent` (recent bekeken gesprekken
  en rapporten, favorieten; #603) bleef staan. Het zijn alleen ID's, maar ze verwijzen naar gesprekken die niet meer
  bestaan en verraden op een gedeeld apparaat dat er met dit account is gewerkt. Na een geslaagde verwijdering wist de
  app de lijst nu ook (`wisRecent`), en de open lijsten in de chat en op `/rapporten` lopen leeg.
- Uitloggen laat de lijst staan zoals in #603; de privacytekst noemt het verschil.
