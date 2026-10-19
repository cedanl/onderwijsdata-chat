// De link naar een bronpagina, voor de bronregel onder een rapportgrafiek (#569) en onder een chatantwoord (#621).
// De server neemt alleen een http(s)-adres uit de catalogus (tools/catalog.py, documentatie_url), maar een spec of een
// bewaard bericht is tekst: een javascript:-, data:- of relatief adres mag nooit een href worden.
const HTTP_URL = /^https?:\/\//i

// Het adres als het een http(s)-adres is, anders null.
export function veiligeBronUrl(url) {
  return typeof url === 'string' && HTTP_URL.test(url) ? url : null
}

const isObject = waarde => typeof waarde === 'object' && waarde !== null && !Array.isArray(waarde)

// `bronlinks` van de server: bronregel → adres, een gewoon object met alleen tekst als waarden.
export function zijnBronlinks(bronlinks) {
  return isObject(bronlinks) && Object.values(bronlinks).every(url => typeof url === 'string')
}

// De veilige link bij één bronregel, of null: dan blijft de regel tekst. Een bericht van vóór #621 heeft geen
// bronlinks, en een bericht uit localStorage of de gespreksopslag kan er iets anders in hebben.
export function bronLink(bronlinks, bron) {
  return isObject(bronlinks) && Object.hasOwn(bronlinks, bron) ? veiligeBronUrl(bronlinks[bron]) : null
}
