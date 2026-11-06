import { useMemo, useState } from 'react'
import TabelScroll from '../../TabelScroll'
import {
  useOpleidingenDashboardData, DashboardShell, SectionHeader, ChartCard, DashboardSources, bronnenVan, fmt, fmtProcent,
} from '../shared/index'

// Het dashboard Opleidingen (#957): per opleiding van een hogeschool of universiteit de cijfers uit de
// Studiekeuzedatabase van LCSK (/api/dashboard/opleidingen, data/dashboard_opleidingen.py). De backend rekent; hier
// staat alleen hoe het eruitziet. Geen rangorde (art. 5 van de leveringsvoorwaarden): de tabel sorteert alleen op
// naam, graad, vorm en plaats, en een cijfer naast landelijk krijgt geen label en geen kleur als oordeel.

const NOOT = { fontSize: '12.5px', color: 'var(--muted-text)', margin: '0 0 12px' }
const TABEL = { width: '100%', borderCollapse: 'collapse', fontSize: '.85rem' }
const CEL = { padding: '5px 8px', verticalAlign: 'top' }
const GETAL = { ...CEL, textAlign: 'right', whiteSpace: 'nowrap' }
const KOP = { ...CEL, textAlign: 'left', borderBottom: '2px solid var(--gray-200)' }
const KOP_GETAL = { ...KOP, textAlign: 'right' }
const RIJ = { borderBottom: '1px solid var(--gray-100)' }
const KLEIN = { fontSize: '12.5px', color: 'var(--muted-text)' }

// De kolommen waarop de tabel sorteert: beschrijvend, geen cijfer (dat zou een rangorde zijn).
export const SORTEERBAAR = { opleiding: 'Opleiding', graad: 'Graad', vorm: 'Vorm', plaats: 'Plaats' }
const VOLGORDE = ['opleiding', 'plaats', 'vorm']
const vergelijk = new Intl.Collator('nl', { sensitivity: 'base', numeric: true }).compare

// Op één beschrijvende kolom, daarna op naam, plaats en vorm, zoals de backend ze geeft.
export function sorteerOpleidingen(rijen, kolom = 'opleiding', oplopend = true) {
  const sleutels = [kolom, ...VOLGORDE.filter(k => k !== kolom)]
  const richting = oplopend ? 1 : -1
  return [...(rijen || [])].sort((a, b) => {
    for (const [i, k] of sleutels.entries()) {
      const verschil = vergelijk(String(a[k] ?? ''), String(b[k] ?? ''))
      if (verschil) return i === 0 ? verschil * richting : verschil
    }
    return 0
  })
}

// Een leeg vak is leeg in de bron: geen cijfer, nooit 0. Zichtbaar een streepje, voor de schermlezer de woorden.
function GeenCijfer() {
  return <><span aria-hidden="true">—</span><span className="sr-only">geen cijfer</span></>
}

export const oordeelTekst = v => (v == null ? null : fmtProcent(v, 2))
export const procentTekst = v => (v == null ? null : `${fmtProcent(v)}%`)

function Waarde({ tekst }) {
  return tekst == null ? <GeenCijfer /> : tekst
}

// Het NSE-oordeel met het aantal respondenten; onder de drempel het woord "onzeker" (geen kleur, #957).
export function nseOnderschrift(rij) {
  if (rij.nse_oordeel == null) return null
  const n = rij.nse_respondenten != null ? `n = ${fmt(rij.nse_respondenten)}` : null
  return [n, rij.nse_onzeker ? 'onzeker' : null].filter(Boolean).join(' · ') || null
}

function NseCel({ rij }) {
  const onder = nseOnderschrift(rij)
  return (
    <td style={GETAL}>
      <Waarde tekst={oordeelTekst(rij.nse_oordeel)} />
      {onder && <div style={KLEIN}>{onder}</div>}
    </td>
  )
}

function LandelijkCel({ waarde, enige }) {
  return (
    <td style={GETAL}>
      <Waarde tekst={waarde} />
      {waarde != null && enige && <div style={KLEIN}>enige aanbieder</div>}
    </td>
  )
}

function SorteerKop({ kolom, sortering, onSorteer }) {
  const actief = sortering.kolom === kolom
  const ariaSort = actief ? (sortering.oplopend ? 'ascending' : 'descending') : 'none'
  return (
    <th scope="col" style={KOP} aria-sort={ariaSort}>
      <button type="button" className="db-sorteerknop" onClick={() => onSorteer(kolom)}>
        {SORTEERBAAR[kolom]}{actief ? (sortering.oplopend ? ' ▲' : ' ▼') : ''}
      </button>
    </th>
  )
}

function Uitleg({ uitleg, sleutels }) {
  const regels = sleutels.map(k => uitleg?.[k]).filter(Boolean)
  if (!regels.length) return null
  return (
    <div className="dashboard-noot" role="note" style={NOOT}>
      {regels.map(r => <p key={r} style={{ margin: '0 0 4px' }}>{r}</p>)}
    </div>
  )
}

// De kop van het dashboard en van de galerijkaart (#933): tellingen, geen rangorde.
export function OpleidingenKerncijfers({ data }) {
  const a = data?.aantallen
  if (!a) return null
  const tegels = [
    ['Opleidingen', a.opleidingen, 'CROHO-codes per plaats'],
    ['Opleidingsvormen', a.vormen, 'voltijd, deeltijd en duaal apart'],
    ['Met NSE-oordeel', a.met_nse, `van de ${fmt(a.vormen)} vormen`],
    ['Met numerus fixus', a.numerus_fixus, 'opleidingen en vormen met loting of selectie'],
  ]
  return (
    <div className="kpi-grid">
      {tegels.map(([label, waarde, sub]) => (
        <div key={label} className="kpi-card">
          <div className="kpi-label">{label}</div>
          <div className="kpi-value">{fmt(waarde)}</div>
          <div className="kpi-sub">{sub}</div>
        </div>
      ))}
    </div>
  )
}

function OpleidingenTabel({ rijen, uitleg }) {
  const [sortering, setSortering] = useState({ kolom: 'opleiding', oplopend: true })
  const gesorteerd = useMemo(
    () => sorteerOpleidingen(rijen, sortering.kolom, sortering.oplopend),
    [rijen, sortering],
  )
  const sorteer = kolom => setSortering(s => ({ kolom, oplopend: s.kolom === kolom ? !s.oplopend : true }))
  if (!rijen?.length) return null
  const kop = { sortering, onSorteer: sorteer }
  return (
    <ChartCard title="Opleidingen" subtitle={`${fmt(rijen.length)} opleidingsvormen, op naam`}>
      <Uitleg uitleg={uitleg} sleutels={['volgorde', 'nse', 'landelijk', 'aantallen', 'doorstroom', 'diplomarendement', 'leeg']} />
      <TabelScroll label="Opleidingen" style={TABEL}>
        <caption className="sr-only">Opleidingen van de instelling per vorm, met het landelijke cijfer ernaast</caption>
        <thead>
          <tr>
            <SorteerKop kolom="opleiding" {...kop} />
            <th scope="col" style={KOP}>CROHO</th>
            <SorteerKop kolom="graad" {...kop} />
            <SorteerKop kolom="vorm" {...kop} />
            <SorteerKop kolom="plaats" {...kop} />
            <th scope="col" style={KOP_GETAL}>Studenten</th>
            <th scope="col" style={KOP_GETAL}>Eerstejaars</th>
            <th scope="col" style={KOP_GETAL}>NSE-oordeel</th>
            <th scope="col" style={KOP_GETAL}>NSE landelijk</th>
            <th scope="col" style={KOP_GETAL}>Doorstroom jaar 2</th>
            <th scope="col" style={KOP_GETAL}>Diplomarendement</th>
            <th scope="col" style={KOP_GETAL}>Rendement landelijk</th>
            <th scope="col" style={KOP_GETAL}>Numerus fixus</th>
          </tr>
        </thead>
        <tbody>
          {gesorteerd.map((r, i) => (
            <tr key={`${r.croho}-${r.plaats}-${r.vorm}-${i}`} style={RIJ}>
              <td style={CEL}>{r.opleiding}</td>
              <td style={CEL}>{r.croho}</td>
              <td style={CEL}>{r.graad}</td>
              <td style={CEL}>{r.vorm}</td>
              <td style={CEL}>{r.plaats ?? <GeenCijfer />}</td>
              <td style={GETAL}><Waarde tekst={r.studenten == null ? null : fmt(r.studenten)} /></td>
              <td style={GETAL}><Waarde tekst={r.eerstejaars == null ? null : fmt(r.eerstejaars)} /></td>
              <NseCel rij={r} />
              <LandelijkCel waarde={oordeelTekst(r.nse_oordeel_landelijk)} enige={r.aanbieders_landelijk === 1} />
              <td style={GETAL}><Waarde tekst={procentTekst(r.doorstroom_jaar2_pct)} /></td>
              <td style={GETAL}><Waarde tekst={procentTekst(r.diploma_opleiding_pct)} /></td>
              <LandelijkCel waarde={procentTekst(r.diploma_opleiding_pct_landelijk)} enige={r.aanbieders_landelijk === 1} />
              <td style={GETAL}>
                {r.numerus_fixus_capaciteit == null ? 'nee' : `${fmt(r.numerus_fixus_capaciteit)} plaatsen`}
                {r.numerus_fixus_studiejaar != null && <div style={KLEIN}>studiejaar {r.numerus_fixus_studiejaar}</div>}
              </td>
            </tr>
          ))}
        </tbody>
      </TabelScroll>
    </ChartCard>
  )
}

// De NSE-thema's per vorm (B4), achter een uitklap: tien kolommen naast de hoofdtabel was te breed.
function ThemaTabel({ rijen, themas }) {
  const metOordeel = (rijen || []).filter(r => themas.some(t => r[t.veld] != null))
  if (!metOordeel.length || !themas.length) return null
  return (
    <details className="chart-card db-uitklap">
      <summary>NSE-thema&apos;s per opleidingsvorm ({fmt(metOordeel.length)})</summary>
      <TabelScroll label="NSE-thema's per opleidingsvorm" style={TABEL}>
        <caption className="sr-only">Gemiddeld oordeel per NSE-thema, schaal 1 tot 5</caption>
        <thead>
          <tr>
            <th scope="col" style={KOP}>Opleiding</th>
            <th scope="col" style={KOP}>Vorm</th>
            <th scope="col" style={KOP_GETAL}>Respondenten</th>
            {themas.map(t => <th key={t.veld} scope="col" style={KOP_GETAL}>{t.naam}</th>)}
          </tr>
        </thead>
        <tbody>
          {metOordeel.map((r, i) => (
            <tr key={`${r.croho}-${r.plaats}-${r.vorm}-${i}`} style={RIJ}>
              <td style={CEL}>{r.opleiding}{r.plaats && <div style={KLEIN}>{r.plaats}</div>}</td>
              <td style={CEL}>{r.vorm}</td>
              <td style={GETAL}>
                <Waarde tekst={r.nse_respondenten == null ? null : fmt(r.nse_respondenten)} />
                {r.nse_onzeker && <div style={KLEIN}>onzeker</div>}
              </td>
              {themas.map(t => <td key={t.veld} style={GETAL}><Waarde tekst={oordeelTekst(r[t.veld])} /></td>)}
            </tr>
          ))}
        </tbody>
      </TabelScroll>
    </details>
  )
}

function ArbeidsmarktTabel({ rijen, uitleg }) {
  if (!rijen?.length) return null
  return (
    <ChartCard title="Arbeidsmarkt van de opleidingsrichting" subtitle="Landelijk per SOI-rubriek, niet de eigen afgestudeerden">
      <Uitleg uitleg={uitleg} sleutels={['arbeidsmarkt', 'leeg']} />
      <TabelScroll label="Arbeidsmarkt van de opleidingsrichting" style={TABEL}>
        <caption className="sr-only">Landelijke arbeidsmarktcijfers van de SOI-rubriek van elke opleiding</caption>
        <thead>
          <tr>
            <th scope="col" style={KOP}>Opleiding</th>
            <th scope="col" style={KOP}>Graad</th>
            <th scope="col" style={KOP}>SOI-rubriek</th>
            <th scope="col" style={KOP_GETAL}>Mediaan salaris (bruto per maand)</th>
            <th scope="col" style={KOP_GETAL}>Werkloos</th>
            <th scope="col" style={KOP_GETAL}>Baan op niveau</th>
            <th scope="col" style={KOP}>Aansluiting studie-baan</th>
          </tr>
        </thead>
        <tbody>
          {rijen.map(r => (
            <tr key={r.croho} style={RIJ}>
              <td style={CEL}>{r.opleiding}<div style={KLEIN}>CROHO {r.croho}</div></td>
              <td style={CEL}>{r.soort_ho} {r.graad}</td>
              {r.reden_leeg
                ? <td style={{ ...CEL, color: 'var(--muted-text)' }} colSpan={5}>{r.reden_leeg}</td>
                : (
                  <>
                    <td style={CEL}>{r.soi_rubriek ?? <GeenCijfer />}</td>
                    <td style={GETAL}><Waarde tekst={r.salaris_mediaan_bruto_maand == null ? null : `€ ${fmt(r.salaris_mediaan_bruto_maand)}`} /></td>
                    <td style={GETAL}><Waarde tekst={procentTekst(r.werkloos_pct)} /></td>
                    <td style={GETAL}><Waarde tekst={procentTekst(r.baan_op_niveau_pct)} /></td>
                    <td style={CEL}>{r.aansluiting_studie_baan ?? <GeenCijfer />}</td>
                  </>
                )}
            </tr>
          ))}
        </tbody>
      </TabelScroll>
    </ChartCard>
  )
}

function NumerusFixusTabel({ rijen, uitleg }) {
  return (
    <ChartCard title="Numerus fixus en decentrale selectie">
      <Uitleg uitleg={uitleg} sleutels={['numerus_fixus']} />
      {rijen?.length ? (
        <TabelScroll label="Numerus fixus" style={TABEL}>
          <caption className="sr-only">Opleidingen met loting of decentrale selectie en hun capaciteit</caption>
          <thead>
            <tr>
              <th scope="col" style={KOP}>Opleiding</th>
              <th scope="col" style={KOP}>Vorm</th>
              <th scope="col" style={KOP}>Voertaal</th>
              <th scope="col" style={KOP_GETAL}>Studiejaar</th>
              <th scope="col" style={KOP_GETAL}>Capaciteit</th>
              <th scope="col" style={KOP}>Aanmelden uiterlijk</th>
            </tr>
          </thead>
          <tbody>
            {rijen.map(r => (
              <tr key={`${r.croho}-${r.vorm}-${r.voertaal}-${r.studiejaar}`} style={RIJ}>
                <td style={CEL}>{r.opleiding}<div style={KLEIN}>CROHO {r.croho}</div></td>
                <td style={CEL}>{r.vorm}</td>
                <td style={CEL}>{r.voertaal ?? <GeenCijfer />}</td>
                <td style={GETAL}>{r.studiejaar ?? <GeenCijfer />}</td>
                <td style={GETAL}><Waarde tekst={r.capaciteit == null ? null : fmt(r.capaciteit)} /></td>
                <td style={CEL}>{r.aanmelden_uiterlijk ?? <GeenCijfer />}</td>
              </tr>
            ))}
          </tbody>
        </TabelScroll>
      ) : (
        <p style={NOOT}>Geen opleidingen met numerus fixus of decentrale selectie in de Studiekeuzedatabase.</p>
      )}
    </ChartCard>
  )
}

export function InlineDashboardOpleidingen({ instelling }) {
  const { data, loading, error, opnieuw } = useOpleidingenDashboardData(instelling)
  const bronnen = bronnenVan([data])
  const peilmoment = bronnen.find(b => b.bron === 'LCSK')?.peilmoment

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error} onOpnieuw={opnieuw}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{data?.instelling || instelling}</span>
          {data?.brin && <span className="meta-badge date">{data.brin}</span>}
          {peilmoment && <span className="meta-badge date">Bron: LCSK Studiekeuzedatabase, {peilmoment}</span>}
        </div>
        {data?.melding && (
          <div className="chart-card" role="status" style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>
            <div style={{ fontSize: '.85rem', color: '#92400E', lineHeight: 1.6 }}>{data.melding}</div>
          </div>
        )}
        {data?.aantallen && (
          <>
            <SectionHeader title="Overzicht" subtitle="Aantallen uit de Studiekeuzedatabase" />
            <OpleidingenKerncijfers data={data} />

            <SectionHeader title="Opleidingen" subtitle="Per opleiding en vorm, met het landelijke cijfer van LCSK ernaast" />
            <OpleidingenTabel rijen={data.opleidingen} uitleg={data.uitleg} />
            <ThemaTabel rijen={data.opleidingen} themas={data.themas || []} />

            <SectionHeader title="Arbeidsmarkt" subtitle="Landelijke cijfers van de opleidingsrichting" />
            <ArbeidsmarktTabel rijen={data.arbeidsmarkt} uitleg={data.uitleg} />

            <SectionHeader title="Toelating" />
            <NumerusFixusTabel rijen={data.numerus_fixus} uitleg={data.uitleg} />
          </>
        )}
        <DashboardSources sources={bronnen} />
      </div>
    </DashboardShell>
  )
}
