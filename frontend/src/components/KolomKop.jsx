// Het model neemt kolomnamen letterlijk uit de bron over in de tabelkop: AANTAL_EERSTEJAARS_INGESCHREVENEN
// zegt een lezer weinig (#222). Een labelbron per kolom is er niet, de naam zelf wel: alleen koppen
// in de vorm HOOFDLETTERS_MET_UNDERSCORE worden zinsnotatie, afkortingen blijven in hoofdletters.
const BRONKOLOM = /^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$/

const AFKORTINGEN = new Set([
  'AOC', 'BBL', 'BOL', 'BRIN', 'CBS', 'CREBO', 'CROHO', 'DUO', 'HBO', 'HO', 'ID', 'ISAT', 'MBO', 'RIO', 'ROC', 'VO', 'WO',
])

export function kolomLabel(kop) {
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
  if (typeof children !== 'string' || !BRONKOLOM.test(children)) return <th {...props}>{children}</th>
  return <th {...props} title={children}>{kolomLabel(children)}</th>
}
