// De naamregel voor een bestandsnaam die uit tekst van de gebruiker komt (#1124, #1125): een rapporttitel of een
// grafiektitel. Tweeling van core/bestandsnaam.py op de server; tests/fixtures/bestandsnamen.json houdt ze gelijk
// (bestandsnaam.test.js en tests/test_bestandsnaam.py lezen hetzelfde bestand).

// Een rapportnaam is hoogstens zoveel tekens vóór de extensie: een bestandssysteem staat 255 bytes toe, en de naam is
// door de regel hieronder alleen ASCII, dus tekens zijn bytes.
export const RAPPORT_MAX = 120
const RAPPORT_ZONDER_TITEL = 'rapport'

// Veilig voor een bestandsnaam: accenten vallen weg (é wordt e), elke reeks andere tekens (spatie, leesteken, een
// emoji) wordt één underscore. Met `maximum` hoogstens zoveel tekens, afgekapt op een woordgrens; zonder woordgrens
// binnen het maximum midden in het woord.
export function bestandsdeel(tekst, maximum) {
  const deel = String(tekst ?? '')
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')
  if (maximum == null || deel.length <= maximum) return deel
  let knip = deel.slice(0, maximum)
  const grens = knip.lastIndexOf('_')
  if (deel[maximum] !== '_' && grens > 0) knip = knip.slice(0, grens)
  return knip.replace(/_+$/, '')
}

// De naam van een rapportdownload zonder extensie (HTML, Markdown en Word): de titel, ingekort, of `rapport`.
export const rapportdeel = titel => bestandsdeel(titel, RAPPORT_MAX) || RAPPORT_ZONDER_TITEL
