// Onderdrukte en ontbrekende cellen (#902). DUO publiceert kleine aantallen niet (-1); de backend telt zo'n cel niet
// mee en meldt per reeks hoeveel lege cellen erin vallen (`onderdrukt`: {jaar: aantal}). Een getal daarover is een
// ondergrens: "ten minste". Een ontbrekend jaar of een ontbrekende sector is een gat, geen 0, en een categorie die
// een grafiek weglaat, wordt genoemd.

export const ONDERDRUKT_UITLEG = 'DUO publiceert kleine aantallen niet; die cellen tellen niet mee'

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
  return <span className="kpi-ondergrens" style={{ fontSize: 'var(--font-klein)', fontWeight: 500, marginRight: 4 }}>ten minste</span>
}

function jarenMetLegeCellen(onderdrukt) {
  return Object.entries(onderdrukt || {})
    .filter(([, n]) => n > 0)
    .map(([jaar]) => jaar)
    .sort((a, b) => Number(a) - Number(b))
}

// Eén regel per reeks met lege cellen: "Ingeschrevenen in 2022, 2023: ten minste (…)".
export function OndergrensNoot({ reeksen }) {
  const regels = (reeksen || [])
    .map(({ label, onderdrukt }) => ({ label, jaren: jarenMetLegeCellen(onderdrukt) }))
    .filter(r => r.jaren.length > 0)
  if (!regels.length) return null
  return (
    <p className="dashboard-noot" role="note" style={{ fontSize: 'var(--font-klein)', color: 'var(--muted-text)', margin: '4px 0 16px' }}>
      {regels.map(r => `${r.label} in ${r.jaren.join(', ')}`).join('; ')}: ten minste ({ONDERDRUKT_UITLEG}).
    </p>
  )
}

// Categorieën (sectoren, hoofdgroepen) waarvan de som een ondergrens is: {categorie: lege cellen}.
export function OndergrensCategorieen({ onderdrukt }) {
  const namen = Object.entries(onderdrukt || {}).filter(([, n]) => n > 0).map(([naam]) => naam)
  if (!namen.length) return null
  return (
    <p className="dashboard-noot" role="note" style={{ fontSize: 'var(--font-klein)', color: 'var(--muted-text)', margin: '8px 0 0' }}>
      Ten minste bij {namen.join(', ')} ({ONDERDRUKT_UITLEG}).
    </p>
  )
}

// Wat een grafiek of tabel weglaat, met de reden.
export function WeggelatenNoot({ namen, reden }) {
  if (!namen?.length) return null
  return (
    <p className="dashboard-noot" role="note" style={{ fontSize: 'var(--font-klein)', color: 'var(--muted-text)', margin: '8px 0 0' }}>
      Niet getoond ({reden}): {namen.join(', ')}.
    </p>
  )
}
