### Limieten: de teller staat onder een HMAC en de privacytekst noemt hem (#1117)
- Met PostgreSQL telt de rate limiter in `rate_limit_hits` onder de kale SHA-256 van de sleutel: bij het inloggen
  `<gebruikersnaam>|<IP-adres>`, bij `/mcp` het IP-adres, bij chat en feedback de gebruikersnaam. Een e-mailadres is met
  één hash terug te rekenen, een IPv4-adres met hooguit 2^32 pogingen. De sleutel is nu een HMAC met een servergeheim
  (`core/pseudoniem.py`, hetzelfde als bij `tokengebruik`, met het domein `ratelimit`).
- Rijen onder de oude sleutel verlopen binnen het venster van de limiet (hoogstens tien minuten); eenmalig begint elke
  teller opnieuw.
- De privacytekst, in de app en in `docs/privacy.md`, noemt de tellers: wat erin staat, onder welke sleutel en hoe lang.
