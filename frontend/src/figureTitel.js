// Plotly breekt een titel niet zelf af (#587): op een telefoon viel het eind van de titel van een
// grafiek in de chat van de figuur ("…, 2020/" in plaats van "…, 2020/2021 – 2024/2025"). Hier wordt
// hij afgebroken met <br>, op de breedte die de grafiek echt heeft.

const BR = /(<br\s*\/?>)/i
const BR_ALLE = /<br\s*\/?>/gi
const TAG = /<[^>]*>/g
const ENTITEIT = /&#?\w+;/g

const REGELAFSTAND = 1.3 // em tussen twee basislijnen, zoals Plotly (LINE_SPACING)
const KAPHOOGTE = 0.7 // em van de bovenkant van een hoofdletter tot de basislijn (Plotly: CAP_SHIFT)
const TITELGROOTTE = 16 // de lettergrootte die create_plot (tools/plot.py) de titel geeft
// Gemiddelde tekenbreedte in em. Gemeten in Chromium (DejaVu Sans): 0,51-0,55 voor gewone titels,
// 0,63 voor hoofdletters; de ruimte die figureLayout rechts van de titel vrijhoudt vangt dat op.
const TEKENBREEDTE = 0.56

// Hoeveel tekens een stuk titel op het scherm beslaat: een tag telt niet, een entiteit als één teken.
function zichtbaar(tekst) {
  return tekst.replace(TAG, '').replace(ENTITEIT, '&').length
}

// De woorden van een regel, gesplitst op spaties buiten tags, zodat <a href="x y"> heel blijft.
function woorden(regel) {
  const uit = []
  let woord = ''
  let inTag = false
  for (const teken of regel) {
    if (teken === '<') inTag = true
    else if (teken === '>') inTag = false
    if (teken !== ' ' || inTag) woord += teken
    else if (woord) {
      uit.push(woord)
      woord = ''
    }
  }
  return woord ? [...uit, woord] : uit
}

// Gulzig vullen. Een woord dat alleen al te lang is, staat heel op een eigen regel: een jaartal
// halveren is erger dan een regel die iets uitsteekt.
function vul(regel, maxTekens) {
  if (zichtbaar(regel) <= maxTekens) return regel
  const regels = []
  for (const woord of woorden(regel)) {
    const laatste = regels.at(-1)
    if (laatste !== undefined && zichtbaar(laatste) + 1 + zichtbaar(woord) <= maxTekens) {
      regels[regels.length - 1] = `${laatste} ${woord}`
    } else {
      regels.push(woord)
    }
  }
  return regels.join('<br>')
}

// De titel in regels van hoogstens maxTekens zichtbare tekens. Een <br> die er al staat blijft; elk
// deel ertussen wordt op zichzelf afgebroken.
export function titelRegels(tekst, maxTekens) {
  if (typeof tekst !== 'string' || !(maxTekens > 0)) return tekst
  return tekst.split(BR).map((deel, i) => (i % 2 ? deel : vul(deel, maxTekens))).join('')
}

export function tekensPerRegel(breedte, grootte) {
  return Math.floor(breedte / (grootte * TEKENBREEDTE))
}

function aantalRegels(tekst) {
  return (tekst.match(BR_ALLE) || []).length + 1
}

function titelGrootte(title) {
  const grootte = title?.font?.size
  return typeof grootte === 'number' && grootte > 0 ? grootte : TITELGROOTTE
}

// De plaats van een titel van meer regels. Plotly zet bij yanchor 'top' de tekst een kaphoogte lager
// (dy), zodat de bovenkant van de hoofdletters op y staat; maar bij meer regels krijgt elke regel een
// eigen y, vervalt die verschuiving en komt de basislijn van de eerste regel op y: die regel valt dan
// half boven de figuur uit. pad.t, dat Plotly bij yanchor 'top' bij y optelt, zet hem terug.
// Zonder eigen plaats zet Plotly de basislijn van de eerste regel midden in de bovenmarge en lopen de
// volgende regels naar beneden, over het plotvlak. Vast aan de bovenkant blijft de eerste regel staan
// waar hij stond, en schuiven de volgende regels en het plotvlak samen omlaag.
function plaatsVoorRegels(title, bovenmarge, grootte) {
  if (title.y == null || title.y === 'auto') {
    return { ...title, yref: 'container', y: 1, yanchor: 'top', pad: { ...title.pad, t: bovenmarge / 2 } }
  }
  if (title.yanchor !== 'top') return title
  return { ...title, pad: { ...title.pad, t: (title.pad?.t ?? 0) + KAPHOOGTE * grootte } }
}

// De titel afgebroken voor een regel van `breedte` pixels, en hoeveel pixels de bovenmarge daarvoor
// hoger moet. Zonder bekende breedte, zonder tekst of op één regel: de titel precies zoals hij was. Het
// titelobject zelf blijft ongemoeid.
export function titelOpBreedte(title, breedte, bovenmarge) {
  const tekst = typeof title === 'string' ? title : title?.text
  if (!(breedte > 0) || typeof tekst !== 'string') return { title, extra: 0 }
  const grootte = titelGrootte(title)
  const text = titelRegels(tekst, tekensPerRegel(breedte, grootte))
  const regels = aantalRegels(text)
  if (regels === 1) return { title, extra: 0 }
  const basis = typeof title === 'string' ? {} : title
  return {
    title: { ...plaatsVoorRegels(basis, bovenmarge, grootte), text },
    extra: (regels - 1) * grootte * REGELAFSTAND,
  }
}
