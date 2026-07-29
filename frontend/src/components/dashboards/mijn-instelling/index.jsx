import { CHART_COLORS } from '../../../constants'
import { Bar, Doughnut } from 'react-chartjs-2'
import {
  useRegioDashboardData, useRendementDashboardData,
  DashboardShell, SectionHeader, RegioBadges, KaartSection,
  useRegioComputed, useDarkMode, fmt,
  buildBarChartData, buildSectorChartData,
  buildMarktaandeelData, buildGroeiRankingData,
  buildMarktaandeelTrendData, buildInstroomRatioData,
  buildSectorTrendData, buildLeerwegenData, buildRendementVergelijkingData,
  chartOpts, doughnutOpts,
  DemografieKpis, InstroomKpis, DiplomeringKpis,
  BenchmarkLineChart, PeerLinesChart,
  MarktaandeelChart, GroeiRankingChart,
  MarktaandeelTrendChart, InstroomRatioChart,
  PeersTable, SectorTrendChart, LeerwegenChart, SectorkamersChart,
  RendementVergelijkingChart,
  barDataLabelsPlugin,
} from '../shared/index'
import { Sparkline } from '../shared/shell'
import { RendementSection } from './rendement-section'
import { GenderSection } from './gender-section'

function SamenvattingTile({ label, eigenWaarde, regioWaarde, regioLabel, sparkValues, color, icon, suffix }) {
  return (
    <div className="kpi-card">
      <div className="kpi-card-header">
        <span className="kpi-label">{label}</span>
        <div className="kpi-icon" style={{ background: `${color}18` }}>{icon}</div>
      </div>
      <div className="kpi-value">{fmt(eigenWaarde)}{suffix}</div>
      {regioWaarde != null && (
        <div className="kpi-trend" style={{ color: '#6B7280' }}>
          {regioLabel}: {fmt(regioWaarde)}
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
  const { data, loading, error } = useRegioDashboardData(instelling)
  const { data: rendData } = useRendementDashboardData(instelling)
  const c = useRegioComputed(data, instelling)
  const dark = useDarkMode()

  const marktData = buildMarktaandeelData(data, instelling, c.dark)
  const marktTrendData = buildMarktaandeelTrendData(data)
  const groeiData = buildGroeiRankingData(data, instelling, c.dark)
  const ratioData = buildInstroomRatioData(data)
  const sectorTrendData = buildSectorTrendData(data?.sectoren_trend)
  const leerwegenData = buildLeerwegenData(data?.leerwegen)
  const rendVergData = buildRendementVergelijkingData(data, instelling, c.dark)

  const bmLabel = c.bmLabel || 'Regio'
  const bm = c.bm || {}
  const bmInges = bm.ingeschrevenen ? Object.values(bm.ingeschrevenen).at(-1) : null
  const bmEj = bm.eerstejaars ? Object.values(bm.eerstejaars).at(-1) : null
  const bmDipl = bm.gediplomeerden ? Object.values(bm.gediplomeerden).at(-1) : null

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={data?.provincie} arbeidsmarktregio={data?.arbeidsmarktregio} bron="DUO Open Onderwijsdata" />

        <KaartSection figureJson={data?.kaart_figure_json} />

        {/* ── Kerncijfers ── */}
        <SectionHeader title="Kerncijfers" subtitle={`${instelling} vs. ${bmLabel.toLowerCase()} — in één oogopslag`} />
        <div className="kpi-grid">
          {c.lastInges && (
            <SamenvattingTile
              label={`Ingeschrevenen ${c.lastInges[0]}`}
              eigenWaarde={c.lastInges[1]}
              regioWaarde={bmInges ? Math.round(bmInges) : null}
              regioLabel={`Gem. ${bmLabel.toLowerCase()}`}
              sparkValues={c.ingesEntries.map(([, v]) => v)}
              color="#2563EB"
              icon={iconPersons('#2563EB')}
            />
          )}
          {c.lastEj && (
            <SamenvattingTile
              label={`Eerstejaars ${c.lastEj[0]}`}
              eigenWaarde={c.lastEj[1]}
              regioWaarde={bmEj ? Math.round(bmEj) : null}
              regioLabel={`Gem. ${bmLabel.toLowerCase()}`}
              sparkValues={c.ejEntries.map(([, v]) => v)}
              color="#22C55E"
              icon={iconChart('#22C55E')}
            />
          )}
          {c.lastDipl && (
            <SamenvattingTile
              label={`Gediplomeerden ${c.lastDipl[0]}`}
              eigenWaarde={c.lastDipl[1]}
              regioWaarde={bmDipl ? Math.round(bmDipl) : null}
              regioLabel={`Gem. ${bmLabel.toLowerCase()}`}
              sparkValues={c.diplEntries.map(([, v]) => v)}
              color="#0D9488"
              icon={iconDiploma('#0D9488')}
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
        <DemografieKpis {...c} nInstellingen={c.bm.n_instellingen} laatsteJaar={data?.laatste_jaar} />
        <PeersTable data={data} instelling={instelling} />
        <PeerLinesChart
          title="Ingeschrevenen per jaar"
          subtitle={c.hasPeers ? `% verandering t.o.v. eerste jaar — ${instelling} (dik) vs. concurrenten in de regio` : `% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`}
          data={c.ingesLineData}
          opts={c.hasPeers ? c.peerOpts : c.indexOpts}
        />
        <InstroomKpis {...c} />
        <BenchmarkLineChart title="Eerstejaars instroom per jaar" subtitle={`% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.ejLineData} indexOpts={c.indexOpts} />
        <MarktaandeelChart data={marktData} jaar={data?.laatste_jaar} dark={c.dark} />
        <MarktaandeelTrendChart data={marktTrendData} dark={c.dark} />
        <GroeiRankingChart data={groeiData} dark={c.dark} />
        <InstroomRatioChart data={ratioData} dark={c.dark} />

        {/* ── Diplomering & rendement ── */}
        <SectionHeader title="Diplomering" subtitle="Gediplomeerden per jaar, vergeleken met de regio" />
        <DiplomeringKpis {...c} rendement={c.rendement} />
        <BenchmarkLineChart title="Gediplomeerden per jaar" subtitle={`% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.diplLineData} indexOpts={c.indexOpts} />
        <RendementVergelijkingChart data={rendVergData} dark={c.dark} />

        <RendementSection data={rendData} instelling={instelling} dark={dark} />

        {/* ── Sectoren ── */}
        <SectionHeader title="Sectoren" subtitle="Verdeling en trend per onderdeel" />
        <SectorTrendChart data={sectorTrendData} dark={c.dark} />
        <LeerwegenChart data={leerwegenData} dark={c.dark} />
        <SectorkamersChart sectorkamers={data?.sectorkamers} dark={c.dark} />

        {/* ── Gender & diversiteit ── */}
        <GenderSection data={data} instelling={instelling} dark={dark} />

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://onderwijsdata.duo.nl/datasets/p01hoinges" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Ingeschrevenen HO per instelling (p01hoinges)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/datasets/p02ho1ejrs" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Eerstejaars HO per instelling (p02ho1ejrs)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/datasets/p04hogdipl" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Gediplomeerden HO per instelling (p04hogdipl)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}
