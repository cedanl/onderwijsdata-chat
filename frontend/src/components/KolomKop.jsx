// Het model neemt kolomnamen letterlijk uit de bron over in de tabelkop: AANTAL_EERSTEJAARS_INGESCHREVENEN
// zegt een lezer weinig (#222). Een labelbron per kolom is er niet, de naam zelf wel: koppen in de vorm
// HOOFDLETTERS_MET_UNDERSCORE en losse woorden in hoofdletters vanaf vier letters worden zinsnotatie,
// afkortingen blijven in hoofdletters. Kortere woorden zijn meestal codes (VT, MAN). Een labelkolom
// (STUDIEJAAR_LABEL, Perioden_label) heet naar wat hij toont. Zelfde regel als tools/kolomlabel.py (#418).
const BRONKOLOM = /^(?:[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+|[A-Z]{4,})$/
const LABELKOLOM = /^(.+)_(?:LABEL|label)$/

const AFKORTINGEN = new Set([
  'AOC', 'BBL', 'BOL', 'BRIN', 'CBS', 'CREBO', 'CROHO', 'DUO', 'HBO', 'HO', 'ID', 'ISAT', 'MBO', 'RIO', 'ROC', 'VO', 'WO',
])

const isBronkolom = kop => BRONKOLOM.test(kop) || LABELKOLOM.test(kop)

export function kolomLabel(kop) {
  const labelkolom = LABELKOLOM.exec(kop)
  if (labelkolom) return kolomLabel(labelkolom[1])
  if (!BRONKOLOM.test(kop)) return kop
  return kop
    .split('_')
    .map((woord, i) => {
      if (AFKORTINGEN.has(woord)) return woord
      const klein = woord.toLowerCase()
      return i === 0 ? klein[0].toUpperCase() + klein.slice(1) : klein
    })
    .join(' ')
}

// eslint-disable-next-line no-unused-vars -- node is react-markdown's AST node, not a DOM attribute
export default function KolomKop({ node, children, ...props }) {
  if (typeof children !== 'string' || !isBronkolom(children)) return <th {...props}>{children}</th>
  return <th {...props} title={children}>{kolomLabel(children)}</th>
}
