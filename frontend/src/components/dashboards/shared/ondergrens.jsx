// Onderdrukte en ontbrekende cellen (#902). DUO publiceert kleine aantallen niet (-1); de backend telt zo'n cel niet
// mee en meldt per reeks hoeveel lege cellen erin vallen (`onderdrukt`: {jaar: aantal}). Een getal daarover is een
// ondergrens: "ten minste". Een ontbrekend jaar of een ontbrekende sector is een gat, geen 0, en een categorie die
// een grafiek weglaat, wordt genoemd.

export const ONDERDRUKT_UITLEG = 'DUO publiceert aantallen van 1 tot en met 4 niet; die cellen tellen niet mee'

// Waarde uit een {jaar: n}-dict, met de jaarsleutel als getal of als tekst.
export function perJaar(dict, jaar) {
  if (!dict || jaar == null) return undefined
  return dict[jaar] ?? dict[String(jaar)]
}

export function isOndergrens(onderdrukt, jaar) {
  return perJaar(onderdrukt, jaar) > 0
}

export function TenMinste({ actief }) {
  if (!actief) return null
  return <span className="kpi-ondergrens" style={{ fontSize: '12.5px', fontWeight: 500, marginRight: 4 }}>ten minste</span>
}

const heeftLegeCellen = onderdrukt => Object.values(onderdrukt || {}).some(n => n > 0)

// De namen van de reeksen in een zin: hoogstens MAX_NAMEN, de rest als aantal. Zo blijft de noot kort, ook bij veel reeksen.
const MAX_NAMEN = 3

export function namenTekst(namen) {
  const uniek = [...new Set(namen)]
  const getoond = uniek.slice(0, MAX_NAMEN)
  const rest = uniek.length - getoond.length
  if (rest > 0) return `${getoond.join(', ')} en ${rest} andere`
  return getoond.length > 1 ? `${getoond.slice(0, -1).join(', ')} en ${getoond.at(-1)}` : getoond.join('')
}

// Eén noot voor alle reeksen met lege cellen (#1145): eerst de boodschap, dan waar het om gaat, in hoogstens twee zinnen
// ongeacht het aantal reeksen en jaren. Per cel staat "ten minste" bij de tegels (TenMinste).
export function OndergrensNoot({ reeksen }) {
  const namen = (reeksen || []).filter(r => heeftLegeCellen(r.onderdrukt)).map(r => r.label)
  if (!namen.length) return null
  return (
    <p className="dashboard-noot" role="note" style={{ fontSize: '12.5px', color: 'var(--muted-text)', margin: '4px 0 16px' }}>
      Sommige totalen zijn een ondergrens: {ONDERDRUKT_UITLEG}. Het gaat om {namenTekst(namen)}.
    </p>
  )
}

// Categorieën (sectoren, hoofdgroepen) waarvan de som een ondergrens is: {categorie: lege cellen}.
export function OndergrensCategorieen({ onderdrukt }) {
  const namen = Object.entries(onderdrukt || {}).filter(([, n]) => n > 0).map(([naam]) => naam)
  if (!namen.length) return null
  return (
    <p className="dashboard-noot" role="note" style={{ fontSize: '12.5px', color: 'var(--muted-text)', margin: '8px 0 0' }}>
      Ten minste bij {namen.join(', ')} ({ONDERDRUKT_UITLEG}).
    </p>
  )
}

// Wat een grafiek of tabel weglaat, met de reden.
export function WeggelatenNoot({ namen, reden }) {
  if (!namen?.length) return null
  return (
    <p className="dashboard-noot" role="note" style={{ fontSize: '12.5px', color: 'var(--muted-text)', margin: '8px 0 0' }}>
      Niet getoond ({reden}): {namen.join(', ')}.
    </p>
  )
}
