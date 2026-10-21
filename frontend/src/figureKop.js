// Boven een rapportgrafiek staat de titel van het model als kop (h3), en create_plot zet een titel in de figuur:
// vaak dezelfde. Op een telefoon kostte die tweede titel 2-3 regels van het plotvlak (#579). Is de figuurtitel gelijk
// aan de kop, dan vervalt hij. Een figuurtitel die meer zegt dan de kop blijft staan. De afrondingsnoot staat
// los hiervan als tekst onder de grafiek (figuurNoot.js, #651).

// Gelijk is gelijk na wat een lezer niet ziet: hoofdletters, witruimte, het soort streepje of apostrof, een punt aan
// het eind, opmaak in de Plotly-titel.
const gewoon = tekst => alsTekst(tekst)
  .normalize('NFKC')
  .toLowerCase()
  .replace(/[‐-―−]/g, '-')
  .replace(/[‘’‛′]/g, "'")
  .replace(/[.:;]+$/, '')

// Plotly-opmaak als platte tekst: een <br> wordt een spatie, tags vallen weg.
export const alsTekst = html => String(html ?? '')
  .replace(/<br\s*\/?>/gi, ' ')
  .replace(/<[^>]*>/g, '')
  .replace(/\s+/g, ' ')
  .trim()

// { figureJson, titelWeg }: de figuur zonder dubbele titel, en of de titel wegviel. Een figuur die niet te lezen is,
// of geen dubbele titel heeft, komt ongewijzigd terug.
export function zonderDubbeleTitel(figureJson, kop) {
  const ongewijzigd = { figureJson, titelWeg: false }
  let figuur
  try {
    figuur = JSON.parse(figureJson)
  } catch {
    return ongewijzigd
  }
  const titel = figuur?.layout?.title
  const tekst = typeof titel === 'string' ? titel : titel?.text
  if (!tekst || !kop || gewoon(tekst) !== gewoon(kop)) return ongewijzigd
  const { title: _, ...layout } = figuur.layout
  return { figureJson: JSON.stringify({ ...figuur, layout }), titelWeg: true }
}
