### API: een onleesbare body geeft de Nederlandse melding van #637 (#1162)
- Een body met ongeldige UTF-8 of JSON die te diep genest is gaf FastAPI's Engelse `400 {"detail": "There was an error
  parsing the body"}`, terwijl gewone ongeldige JSON al de Nederlandse 422 kreeg. Beide krijgen nu dezelfde 422
  "Ongeldige invoer. Controleer de gegevens en probeer opnieuw."
