// Npuls-huisstijl voor de PDF van het rapport (#1037): kleuren, letter en logo, één bron voor reportHtml.js en
// de tests. Bron: de npuls-huisstijl-skill (SKILL.md, assets/shared/logos/npuls-logo.svg). Geen @font-face en geen
// extern bestand: General Sans staat alleen in de lettervolgorde, zonder die letter valt de PDF terug op Inter of
// Arial, en het logo staat inline in het rapport, dus de CSP van het rapportframe blijft zoals hij is.
export const NPULS = {
  oranje: '#DD784B',
  zwart: '#000000',
  wit: '#FFFFFF',
  roze: '#F4D9DC',
  blauw: '#3D68EC',
}

// De naam naast het logo in de kop van de PDF van een rapport (reportHtml.js) en van een dashboard (DashboardPrintkop.jsx).
export const NPULS_PRODUCTNAAM = 'EDUdata'

export const NPULS_LETTER = '"General Sans",Inter,Arial,sans-serif'

// Het beeldmerk, zwart. De cirkels zoals in het bronbestand; op het svg-element zelf is xmlns weg (een inline svg
// in HTML heeft die niet nodig, en zo staat er geen adres in het rapport) en role/aria-label vervangen door
// aria-hidden: de naam "EDUdata" staat ernaast als tekst.
export const NPULS_LOGO_SVG = '<svg viewBox="0 0 72 72" aria-hidden="true" focusable="false"><g fill="#000000">'
  + '<circle cx="36.0" cy="29.0" r="3.0"/><circle cx="42.1" cy="32.5" r="3.0"/><circle cx="42.1" cy="39.5" r="3.0"/>'
  + '<circle cx="36.0" cy="43.0" r="3.0"/><circle cx="29.9" cy="39.5" r="3.0"/><circle cx="29.9" cy="32.5" r="3.0"/>'
  + '<circle cx="36.0" cy="23.0" r="2.5"/><circle cx="43.6" cy="25.5" r="2.5"/><circle cx="48.4" cy="32.0" r="2.5"/>'
  + '<circle cx="48.4" cy="40.0" r="2.5"/><circle cx="43.6" cy="46.5" r="2.5"/><circle cx="36.0" cy="49.0" r="2.5"/>'
  + '<circle cx="28.4" cy="46.5" r="2.5"/><circle cx="23.6" cy="40.0" r="2.5"/><circle cx="23.6" cy="32.0" r="2.5"/>'
  + '<circle cx="28.4" cy="25.5" r="2.5"/><circle cx="36.0" cy="17.0" r="2.0"/><circle cx="44.2" cy="18.9" r="2.0"/>'
  + '<circle cx="50.9" cy="24.2" r="2.0"/><circle cx="54.5" cy="31.8" r="2.0"/><circle cx="54.5" cy="40.2" r="2.0"/>'
  + '<circle cx="50.9" cy="47.8" r="2.0"/><circle cx="44.2" cy="53.1" r="2.0"/><circle cx="36.0" cy="55.0" r="2.0"/>'
  + '<circle cx="27.8" cy="53.1" r="2.0"/><circle cx="21.1" cy="47.8" r="2.0"/><circle cx="17.5" cy="40.2" r="2.0"/>'
  + '<circle cx="17.5" cy="31.8" r="2.0"/><circle cx="21.1" cy="24.2" r="2.0"/><circle cx="27.8" cy="18.9" r="2.0"/>'
  + '<circle cx="36.0" cy="11.0" r="1.6"/><circle cx="44.6" cy="12.5" r="1.6"/><circle cx="52.1" cy="16.8" r="1.6"/>'
  + '<circle cx="57.7" cy="23.5" r="1.6"/><circle cx="60.6" cy="31.7" r="1.6"/><circle cx="60.6" cy="40.3" r="1.6"/>'
  + '<circle cx="57.7" cy="48.5" r="1.6"/><circle cx="52.1" cy="55.2" r="1.6"/><circle cx="44.6" cy="59.5" r="1.6"/>'
  + '<circle cx="36.0" cy="61.0" r="1.6"/><circle cx="27.4" cy="59.5" r="1.6"/><circle cx="19.9" cy="55.2" r="1.6"/>'
  + '<circle cx="14.3" cy="48.5" r="1.6"/><circle cx="11.4" cy="40.3" r="1.6"/><circle cx="11.4" cy="31.7" r="1.6"/>'
  + '<circle cx="14.3" cy="23.5" r="1.6"/><circle cx="19.9" cy="16.8" r="1.6"/><circle cx="27.4" cy="12.5" r="1.6"/>'
  + '<circle cx="36.0" cy="5.0" r="1.2"/><circle cx="44.7" cy="6.3" r="1.2"/><circle cx="52.8" cy="9.9" r="1.2"/>'
  + '<circle cx="59.4" cy="15.7" r="1.2"/><circle cx="64.2" cy="23.1" r="1.2"/><circle cx="66.7" cy="31.6" r="1.2"/>'
  + '<circle cx="66.7" cy="40.4" r="1.2"/><circle cx="64.2" cy="48.9" r="1.2"/><circle cx="59.4" cy="56.3" r="1.2"/>'
  + '<circle cx="52.8" cy="62.1" r="1.2"/><circle cx="44.7" cy="65.7" r="1.2"/><circle cx="36.0" cy="67.0" r="1.2"/>'
  + '<circle cx="27.3" cy="65.7" r="1.2"/><circle cx="19.2" cy="62.1" r="1.2"/><circle cx="12.6" cy="56.3" r="1.2"/>'
  + '<circle cx="7.8" cy="48.9" r="1.2"/><circle cx="5.3" cy="40.4" r="1.2"/><circle cx="5.3" cy="31.6" r="1.2"/>'
  + '<circle cx="7.8" cy="23.1" r="1.2"/><circle cx="12.6" cy="15.7" r="1.2"/><circle cx="19.2" cy="9.9" r="1.2"/>'
  + '<circle cx="27.3" cy="6.3" r="1.2"/>'
  + '</g></svg>'
