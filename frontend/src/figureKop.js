// Boven een rapportgrafiek staat de titel van het model als kop (h3), en create_plot zet een titel in de figuur:
// vaak dezelfde. Op een telefoon kostte die tweede titel 2-3 regels van het plotvlak (#579). Is de figuurtitel gelijk
// aan de kop, dan vervalt hij; de noot eronder (de CBS-afronding, #352) komt als tekst onder de kop, zodat hij bij de
// grafiek blijft. Een figuurtitel die meer zegt dan de kop blijft staan.

// Gelijk is gelijk na wat een lezer niet ziet: hoofdletters, witruimte, het soort streepje of apostrof, een punt aan
// het eind, opmaak in de Plotly-titel.
const gewoon = tekst => alsTekst(tekst)
  .normalize('NFKC')
  .toLowerCase()
  .replace(/[‐-―−]/g, '-')
  .replace(/[‘’‛′]/g, "'")
  .replace(/[.:;]+$/, '')

const alsTekst = html => String(html ?? '')
  .replace(/<br\s*\/?>/gi, ' ')
  .replace(/<[^>]*>/g, '')
  .replace(/\s+/g, ' ')
  .trim()

// { figureJson, noot, titelWeg }: de figuur zonder dubbele titel, de noot als platte tekst ('' zonder), en of de
// titel wegviel. Een figuur die niet te lezen is, of geen dubbele titel heeft, komt ongewijzigd terug.
export function zonderDubbeleTitel(figureJson, kop) {
  const ongewijzigd = { figureJson, noot: '', titelWeg: false }
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
  return { figureJson: JSON.stringify({ ...figuur, layout }), noot: alsTekst(titel?.subtitle?.text), titelWeg: true }
}
