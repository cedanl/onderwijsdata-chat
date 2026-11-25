### Geen tokenbudget voor `demo` op test
- Het gedeelde account `demo` heeft op de testomgeving geen tokenbudget meer, omdat het tijdens audits aan de 6 mln
  per dag zat en zo andere testers tegenhield. Elk ander account houdt het budget; het gebruik van `demo` telt nog wel
  mee. Een nieuwe instelling `TOKENBUDGET_VRIJGESTELD` noemt de vrijgestelde accounts; playground en productie zetten
  haar niet.
