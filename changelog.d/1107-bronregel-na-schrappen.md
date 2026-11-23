### Chat: na het schrappen van ongedekte getallen blijft geen antwoord met alleen een bronregel over (#1107)
- Haalt de controle de zinnen met een getal weg dat niet in de opgehaalde data staat, en blijft er alleen een
  `Bron:`-regel, een Bronnen-sectie of een kopje over, dan houdt de app het antwoord in, met de redenen. Eerder bleef
  zo'n bronregel staan als enig antwoord, met een tabel als bron die de cijfers niet bevatte.
- Een `Bron:`-regel telt bij het tellen van wat wegvalt en wat blijft als één regel, ook als er een puntkomma in staat.
