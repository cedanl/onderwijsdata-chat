### Inloggen met SRAM: PKCE, nonce en een gecontroleerd id_token (#1024)
- De SRAM-login stuurt nu een PKCE-challenge (S256) en een nonce mee. State, nonce en verifier staan elk kort in een
  eigen cookie (`HttpOnly`, `Secure`, `SameSite=Lax`, 10 minuten); de callback wist ze alle drie, ook als de login
  mislukt.
- De callback controleert het `id_token` van SRAM: de handtekening tegen de sleutels uit de discovery, de uitgever, de
  client, de vervaltijd en de nonce. Noemt `userinfo` een andere gebruiker (`sub`) dan het token, dan volgt geen
  login. Een ongeldige login geeft 400 zonder sessie; een fout van SRAM zelf stuurt zoals eerder terug naar
  `/?oidc_error=1`. De gebruikersnaam blijft het e-mailadres (S21).
- Nog te doen vóór de promotie naar playground: een SRAM-login op test, want geeft de SRAM-proxy geen `id_token` of
  een onverwacht algoritme, dan kan niemand via SRAM inloggen (SECURITY.md S28).
