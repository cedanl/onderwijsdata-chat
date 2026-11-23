### Tokengebruik: de sleutel is een HMAC met een servergeheim, geen kale hash (#1112)
- `tokengebruik` bewaarde het verbruik per account onder de kale SHA-256 van de accountnaam, met SRAM een e-mailadres:
  wie de database of een back-up had, bevestigde met één hash of iemand de app gebruikte. De sleutel is nu een HMAC met
  een servergeheim (`core/pseudoniem.py`, afgeleid van `CHAT_SECRET`, met het domein `tokengebruik` erbij).
- De rijen onder de oude sleutel gaan bij de eerste start weg (de kale hash is niet naar de nieuwe om te zetten zonder
  de accountnamen): de dag- en maandteller beginnen eenmalig opnieuw. Wie `CHAT_SECRET` roteert, zet de tellers ook op
  nul.
- Buiten `local` waarschuwt de start als `CHAT_SECRET` leeg is (alleen een openbare demo zonder login komt daar).
