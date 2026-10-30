### Accreditatiedata per ho-opleiding uit DUO (#726, stap A)
- De chattool `get_accreditatie` geeft voor één hbo- of wo-opleiding bij één instelling de datums die DUO over de
  accreditatie registreert (Overzicht Erkenningen ho, CC-BY, dagelijks bijgewerkt): de besluitdatum van de NVAO, de
  begindatum, de uiterste indiening voor de volgende beoordeling en, waar DUO ze vult, voorwaarden, verlenging (met de
  WHW-grond), intrekking, afbouw en de vervaldatum van een nieuwe opleiding. Elke datum krijgt zijn betekenis uit code.
- De uiterste indiening van het visitatierapport heet nooit einddatum of "geaccrediteerd tot"; ligt ze in het
  verleden, dan zegt een noot dat de accreditatie daarmee niet verlopen is.
- Er zit geen NVAO-oordeel in, en dat zegt de tool zelf. De Inspectietool, de systeemprompt en de docs verwijzen voor
  hbo en wo nu naar `get_accreditatie`; de NVAO-oordelen wachten op toestemming van de NVAO (stap B).
- De opleiding is te vinden op naam of CROHO-code (vijf cijfers met voorloopnullen). Passen er meer, dan noemt de
  melding ze met niveau en code. Onder het antwoord staat de bronregel "DUO · Overzicht Erkenningen ho, versie van …".
