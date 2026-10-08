// Zichtbare citaties (#365, #415): de server stuurt per gecontroleerd getal de meetwaarde mee
// waar het uit komt, of dat de herkomst niet is vastgesteld (agent/citaties.py). Dit
// rehype-plugin zet precies die getallen om in een element met de herkomst erbij; getallen
// zonder citatie en getallen in code blijven tekst.
const GEEN_CITATIE = new Set(['code', 'pre'])

function escape(tekst) {
  return tekst.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// Zelfde afbakening als de getalcontrole: niet vast aan een letter, cijfer, punt of komma.
function patroon(citaties) {
  const getallen = citaties.map(c => escape(c.getal)).sort((a, b) => b.length - a.length)
  return new RegExp(`(?<![\\w.,])(?:${getallen.join('|')})(?![\\w]|,\\d)`, 'g')
}

function citatieElement(c) {
  return {
    type: 'element',
    tagName: 'span',
    properties: {
      dataCitatie: c.getal,
      ...(c.vastgesteld === false && { dataOnbepaald: c.reden || '' }),
      ...((c.label || c.tool) && { dataLabel: c.label || c.tool }),
      ...(c.stap && { dataStap: String(c.stap) }),
      ...(c.bron && { dataBron: c.bron }),
      ...(c.selectie && { dataSelectie: c.selectie }),
      ...(c.maat && { dataMaat: c.eenheid ? `${c.maat} (${c.eenheid})` : c.maat }),
      ...(c.data_key && { dataKey: c.data_key }),
    },
    children: [{ type: 'text', value: c.getal }],
  }
}

// De server geeft per voorkomen een citatie, in tekstvolgorde (CH-08): het k-de voorkomen van een
// getal krijgt de k-de citatie met dat getal. `teller` telt over de hele tekst.
export function splitTekst(tekst, citaties, regex, teller = new Map()) {
  const delen = []
  let van = 0
  for (const m of tekst.matchAll(regex)) {
    if (m.index > van) delen.push({ type: 'text', value: tekst.slice(van, m.index) })
    const n = teller.get(m[0]) ?? 0
    teller.set(m[0], n + 1)
    const metGetal = citaties.filter(c => c.getal === m[0])
    delen.push(citatieElement(metGetal[n] ?? metGetal.at(-1)))
    van = m.index + m[0].length
  }
  if (van === 0) return null
  if (van < tekst.length) delen.push({ type: 'text', value: tekst.slice(van) })
  return delen
}

function verwerk(node, citaties, regex, teller) {
  if (!node.children || GEEN_CITATIE.has(node.tagName)) return
  node.children = node.children.flatMap(kind => {
    if (kind.type === 'text') return splitTekst(kind.value, citaties, regex, teller) ?? [kind]
    verwerk(kind, citaties, regex, teller)
    return [kind]
  })
}

export function rehypeCitaties(citaties) {
  return () => {
    if (!citaties?.length) return () => {}
    const regex = patroon(citaties)
    return tree => verwerk(tree, citaties, regex, new Map())
  }
}
