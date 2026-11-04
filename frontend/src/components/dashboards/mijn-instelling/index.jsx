import { useMemo } from 'react'
import { COLOR_EIGEN, COLOR_DIPLOM, COLOR_EERSTEJAARS } from '../../../constants'
import {
  useRegioDashboardData, useRendementDashboardData,
  DashboardShell, SectionHeader, RegioBadges, DashboardSources, KaartSection,
  BRONNEN_HO, BRONNEN_MBO,
  useRegioComputed, useDarkMode, fmt, Sparkline,
  buildMarktaandeelData, buildGroeiRankingData,
  buildMarktaandeelTrendData, buildInstroomRatioData,
  buildSectorTrendData, buildLeerwegenData, buildRendementVergelijkingData,
  DemografieKpis, InstroomKpis, DiplomeringKpis,
  BenchmarkLineChart, PeerLinesChart,
  MarktaandeelChart, GroeiRankingChart,
  MarktaandeelTrendChart, InstroomRatioChart,
  PeersTable, SectorTrendChart, LeerwegenChart, HoofdgroepenChart,
  RendementVergelijkingChart, NietGeladen, DeelLading, gatenVan,
  sortedEntries, perJaar, isOndergrens, TenMinste, OndergrensNoot,
} from '../shared/index'

// Van /api/dashboard/regio toont dit dashboard de DUO-onderdelen; UWV en ROA staan op het arbeidsmarktdashboard.
const REGIO_BRONNEN = ['DUO']
import { RendementSection } from './rendement-section'
import { GenderSection } from './gender-section'

function SamenvattingTile({ label, eigenWaarde, regioWaarde, regioLabel, sparkValues, color, icon, suffix, ondergrens, regioOndergrens }) {
  return (
    <div className="kpi-card">
      <div className="kpi-card-header">
        <span className="kpi-label">{label}</span>
        <div className="kpi-icon" style={{ background: `${color}18` }}>{icon}</div>
      </div>
      <div className="kpi-value"><TenMinste actief={ondergrens} />{fmt(eigenWaarde)}{suffix}</div>
      {regioWaarde != null && (
        <div className="kpi-trend" style={{ color: 'var(--gray-500)' }}>
          {regioLabel}: {regioOndergrens ? 'ten minste ' : ''}{fmt(regioWaarde)}
        </div>
      )}
      {sparkValues && <Sparkline values={sparkValues} color={color} />}
    </div>
  )
}

const iconPersons = (color) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
)
const iconChart = (color) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
)
const iconDiploma = (color) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
)
const iconGender = (color) => (
  <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
)

export function InlineDashboardMijnInstelling({ instelling }) {
  const { data, loading, error, opnieuw } = useRegioDashboardData(instelling)
  const rendement = useRendementDashboardData(instelling)
  const rendData = rendement.data
  const gaten = gatenVan([data, rendData], REGIO_BRONNEN)
  const allesOpnieuw = () => { opnieuw(); rendement.opnieuw() }
  const c = useRegioComputed(data, instelling)
  const dark = useDarkMode()

  const {
    marktData, marktTrendData, groeiData, ratioData, sectorTrendData, leerwegenData, rendVergData,
  } = useMemo(() => ({
    marktData: buildMarktaandeelData(data, instelling, c.dark),
    marktTrendData: buildMarktaandeelTrendData(data),
    groeiData: buildGroeiRankingData(data, instelling, c.dark),
    ratioData: buildInstroomRatioData(data),
    sectorTrendData: buildSectorTrendData(data?.sectoren_trend),
    leerwegenData: buildLeerwegenData(data?.leerwegen),
    rendVergData: buildRendementVergelijkingData(data, instelling, c.dark),
  }), [data, instelling, c.dark])

  const bmLabel = c.bmLabel || 'Regio'
  const bm = c.bm || {}
  // Onderdrukte cellen per reeks en jaar (#902): een getal daarover is "ten minste".
  const od = data?.onderdrukt || {}
  const bmOd = bm.onderdrukt || {}
  const bmLaatste = sleutel => sortedEntries(bm[sleutel]).at(-1) ?? [null, null]
  const [bmIngesJaar, bmInges] = bmLaatste('ingeschrevenen')
  const [bmEjJaar, bmEj] = bmLaatste('eerstejaars')
  const [bmDiplJaar, bmDipl] = bmLaatste('gediplomeerden')
  // Het aantal peers achter het gemiddelde van dat jaar (#903): niet elke peer heeft elk jaar data.
  const gemLabel = (sleutel, jaar) => {
    const n = perJaar(bm.n_per_jaar?.[sleutel], jaar)
    return `Gem. ${bmLabel.toLowerCase()}${n != null ? ` (${n} instellingen)` : ''}`
  }
  const vanaf = startjaar => (startjaar != null ? `% verandering t.o.v. ${startjaar}` : '% verandering')
  const noot = (sleutel, label) => [
    { label, onderdrukt: od[sleutel] },
    { label: `${label} ${bmLabel.toLowerCase()}`, onderdrukt: bmOd[sleutel] },
  ]
  const sectorNoot = Object.entries(od.sectoren_trend || {}).map(([s, onderdrukt]) => ({ label: s, onderdrukt }))

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error} onOpnieuw={opnieuw}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={data?.provincie} arbeidsmarktregio={data?.arbeidsmarktregio} bron="DUO Open Onderwijsdata" />
        <NietGeladen onderdelen={gaten} onOpnieuw={allesOpnieuw} />

        <KaartSection figureJson={data?.kaart_figure_json} />

        {/* ── Kerncijfers ── */}
        <SectionHeader title="Kerncijfers" subtitle={`${instelling} vs. ${bmLabel.toLowerCase()} — in één oogopslag`} />
        <div className="kpi-grid">
          {c.lastInges && (
            <SamenvattingTile
              label={`Ingeschrevenen ${c.lastInges[0]}`}
              eigenWaarde={c.lastInges[1]}
              regioWaarde={bmInges ? Math.round(bmInges) : null}
              regioLabel={gemLabel('ingeschrevenen', bmIngesJaar)}
              sparkValues={c.ingesEntries.map(([, v]) => v)}
              color={COLOR_EIGEN}
              icon={iconPersons(COLOR_EIGEN)}
              ondergrens={isOndergrens(od.ingeschrevenen, c.lastInges[0])}
              regioOndergrens={isOndergrens(bmOd.ingeschrevenen, bmIngesJaar)}
            />
          )}
          {c.lastEj && (
            <SamenvattingTile
              label={`Eerstejaars ${c.lastEj[0]}`}
              eigenWaarde={c.lastEj[1]}
              regioWaarde={bmEj ? Math.round(bmEj) : null}
              regioLabel={gemLabel('eerstejaars', bmEjJaar)}
              sparkValues={c.ejEntries.map(([, v]) => v)}
              color={COLOR_EERSTEJAARS}
              icon={iconChart(COLOR_EERSTEJAARS)}
              ondergrens={isOndergrens(od.eerstejaars, c.lastEj[0])}
              regioOndergrens={isOndergrens(bmOd.eerstejaars, bmEjJaar)}
            />
          )}
          {c.lastDipl && (
            <SamenvattingTile
              label={`Gediplomeerden ${c.lastDipl[0]}`}
              eigenWaarde={c.lastDipl[1]}
              regioWaarde={bmDipl ? Math.round(bmDipl) : null}
              regioLabel={gemLabel('gediplomeerden', bmDiplJaar)}
              sparkValues={c.diplEntries.map(([, v]) => v)}
              color={COLOR_DIPLOM}
              icon={iconDiploma(COLOR_DIPLOM)}
              ondergrens={isOndergrens(od.gediplomeerden, c.lastDipl[0])}
              regioOndergrens={isOndergrens(bmOd.gediplomeerden, bmDiplJaar)}
            />
          )}
          {c.pctVrouw != null && (
            <SamenvattingTile
              label={`Aandeel vrouw ${data?.laatste_jaar}`}
              eigenWaarde={c.pctVrouw}
              suffix="%"
              regioWaarde={null}
              regioLabel=""
              color="#F59E0B"
              icon={iconGender('#F59E0B')}
            />
          )}
        </div>

        {/* ── Instroom & demografie ── */}
        <SectionHeader title="Instroom & demografie" subtitle="Ingeschrevenen, eerstejaars en regionale vergelijking" />
        <DemografieKpis {...c} nInstellingen={perJaar(bm.n_per_jaar?.ingeschrevenen, c.totaalRegioJaar) ?? bm.n_instellingen} laatsteJaar={data?.laatste_jaar} />
        <OndergrensNoot reeksen={noot('ingeschrevenen', 'Ingeschrevenen')} />
        <PeersTable data={data} instelling={instelling} />
        <PeerLinesChart
          title="Ingeschrevenen per jaar"
          subtitle={start => (c.hasPeers ? `${vanaf(start)} — ${instelling} (dik) vs. concurrenten in de regio` : `${vanaf(start)} — eigen instelling vs. ${c.bmLabel.toLowerCase()}`)}
          data={c.ingesLineData}
          opts={c.hasPeers ? c.peerOpts : c.indexOpts}
        />
        <InstroomKpis {...c} />
        <OndergrensNoot reeksen={noot('eerstejaars', 'Eerstejaars')} />
        <BenchmarkLineChart title="Eerstejaars instroom per jaar" subtitle={start => `${vanaf(start)} — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.ejLineData} indexOpts={c.indexOpts} />
        <MarktaandeelChart data={marktData} jaar={data?.laatste_jaar} dark={c.dark} />
        <MarktaandeelTrendChart data={marktTrendData} dark={c.dark} />
        <GroeiRankingChart data={groeiData} dark={c.dark} />
        <InstroomRatioChart data={ratioData} dark={c.dark} />

        {/* ── Diplomering & rendement ── */}
        <SectionHeader title="Diplomering" subtitle="Gediplomeerden per jaar, vergeleken met de regio" />
        <DiplomeringKpis {...c} rendement={c.rendement} />
        <OndergrensNoot reeksen={noot('gediplomeerden', 'Gediplomeerden')} />
        <BenchmarkLineChart title="Gediplomeerden per jaar" subtitle={start => `${vanaf(start)} — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.diplLineData} indexOpts={c.indexOpts} />
        <RendementVergelijkingChart data={rendVergData} dark={c.dark} />

        <DeelLading titel="Diplomarendement" loading={rendement.loading} error={rendement.error} onOpnieuw={rendement.opnieuw} hoogte={320}>
          <RendementSection data={rendData} instelling={instelling} dark={dark} />
        </DeelLading>

        {/* ── Sectoren ── */}
        <SectionHeader title="Sectoren" subtitle="Verdeling en trend per onderdeel" />
        <SectorTrendChart data={sectorTrendData} dark={c.dark} />
        <LeerwegenChart data={leerwegenData} dark={c.dark} />
        <HoofdgroepenChart perHoofdgroep={data?.ingeschrevenen_per_hoofdgroep} onderdrukt={od.ingeschrevenen_per_hoofdgroep} dark={c.dark} />
        <OndergrensNoot reeksen={sectorNoot} />

        {/* ── Gender & diversiteit ── */}
        <GenderSection data={data} instelling={instelling} dark={dark} />

        <DashboardSources sources={data?.type === 'mbo' ? BRONNEN_MBO : BRONNEN_HO} />
      </div>
    </DashboardShell>
  )
}
