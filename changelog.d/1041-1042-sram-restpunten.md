### SRAM-login: restpunten na PKCE en nonce (#1041, #1042)
- De login-cookies worden ook na een onverwachte fout in de callback verwijderd; de gebruiker krijgt dan een 500 met een
  fout-ID in plaats van cookies die nog 10 minuten blijven staan.
- Een discovery-document waarvan de `issuer` niet bij de discovery-URL hoort, start geen login (OIDC Discovery §4.3).
- Een id_token met een onbekende sleutel (`kid`) laat de app de sleutels van SRAM hooguit één keer per minuut opnieuw
  ophalen.
- De privacytekst in de app noemt de drie login-cookies (OIDC-state, nonce, PKCE-verifier), zoals `docs/privacy.md`.
