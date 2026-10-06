// Zichtbare citaties (#365): de server stuurt per gecontroleerd getal de toolstap mee
// (agent/citaties.py). Dit rehype-plugin zet precies die getallen om in een element met de
// herkomst erbij; getallen zonder citatie en getallen in code blijven tekst.
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
      dataLabel: c.label || c.tool,
      ...(c.bron && { dataBron: c.bron }),
      ...(c.data_key && { dataKey: c.data_key }),
    },
    children: [{ type: 'text', value: c.getal }],
  }
}

export function splitTekst(tekst, citaties, regex) {
  const delen = []
  let van = 0
  for (const m of tekst.matchAll(regex)) {
    if (m.index > van) delen.push({ type: 'text', value: tekst.slice(van, m.index) })
    delen.push(citatieElement(citaties.find(c => c.getal === m[0])))
    van = m.index + m[0].length
  }
  if (van === 0) return null
  if (van < tekst.length) delen.push({ type: 'text', value: tekst.slice(van) })
  return delen
}

function verwerk(node, citaties, regex) {
  if (!node.children || GEEN_CITATIE.has(node.tagName)) return
  node.children = node.children.flatMap(kind => {
    if (kind.type === 'text') return splitTekst(kind.value, citaties, regex) ?? [kind]
    verwerk(kind, citaties, regex)
    return [kind]
  })
}

export function rehypeCitaties(citaties) {
  return () => {
    if (!citaties?.length) return () => {}
    const regex = patroon(citaties)
    return tree => verwerk(tree, citaties, regex)
  }
}
