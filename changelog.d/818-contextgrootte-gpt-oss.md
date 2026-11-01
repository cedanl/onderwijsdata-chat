### GPT-OSS via Willma krijgt zijn echte contextgrootte (#818)
- De vaste contextgrootte voor GPT-OSS 120B stond onder een andere model-ID dan de app gebruikt
  (`openai/gpt-oss-120b` in plaats van `openai/openai/gpt-oss-120b`), met 4.096 tokens. Met Willma viel het model zo
  stil terug op 4.096 tokens per antwoord, met een WARNING. Nu geldt de context uit de modelkaart (131.072 tokens),
  dus `MAX_TOKENS` (standaard 40.960) wordt niet meer afgekapt. De omgevingen draaien nu op Azure AI; daar verandert
  niets.
