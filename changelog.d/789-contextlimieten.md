### Een heropend lang gesprek houdt zijn eerste vraag, en de contextlimieten komen van de server (#789)
- Een lang gesprek dat je heropent, verloor zijn eerste vraag: browser en server lieten bij het inkorten de oudste
  berichten vallen, terwijl het live gesprek de eerste vraag vasthield. Die vraag is het onderwerp van rapport en
  dashboard. Nu korten live, heropend en de browser op dezelfde manier in (`agent/history.py` `trim`, in de browser
  `contextLimits.js` `trimHistory`): de eerste vraag blijft, daarna de jongste berichten.
- `/api/config` publiceert `max_chat_turns` en `max_history`. De chat gebruikt die in plaats van eigen vaste getallen,
  zoals al bij `max_message_chars`; de constanten in de frontend zijn alleen nog de terugval. Het aantal vragen per
  gesprek is `MAX_HISTORY // 2` (een vraag en zijn antwoord), zodat een andere `MAX_HISTORY` ook de chat volgt.
- De melding bij een (bijna) volle chat zegt "20 vragen" in plaats van "20 berichten": ze telde al vragen.
- De tekstlimiet van algemene feedback staat in de frontend bij de andere limieten; een test houdt hem gelijk aan
  die van de server.
