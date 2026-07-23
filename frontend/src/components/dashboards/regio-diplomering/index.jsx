import { CHART_COLORS } from '../../../constants'
import { Bar } from 'react-chartjs-2'
import {
  useRegioDashboardData, DashboardShell,
  buildBarChartData, buildSectorTrendData, buildLeerwegenData, buildRendementVergelijkingData,
  useRegioComputed, SectionHeader, RegioBadges,
  DiplomeringKpis,
  BenchmarkLineChart, KaartSection,
  SectorTrendChart, LeerwegenChart, RendementVergelijkingChart,
} from '../shared/index'

export function InlineDashboardRegioDiplomering({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const c = useRegioComputed(data, instelling)
  const sectorTrendData = buildSectorTrendData(data?.sectoren_trend)
  const leerwegenData = buildLeerwegenData(data?.leerwegen)
  const rendVergData = buildRendementVergelijkingData(data, instelling, c.dark)

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={data?.provincie} arbeidsmarktregio={data?.arbeidsmarktregio} bron="DUO Open Onderwijsdata" />

        <KaartSection figureJson={data?.kaart_figure_json} />

        <SectionHeader title="Voortgang" subtitle="Inschrijvingen en sectoren per onderdeel" />
        <div className="charts-grid">
          {data?.ingeschrevenen && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Inschrijvingen trend</div><div className="chart-sub">{instelling} (alle jaren)</div></div></div>
              <div style={{ height: 200 }}><Bar data={buildBarChartData(data?.ingeschrevenen, 'Ingeschrevenen', CHART_COLORS[0])} options={c.opts} /></div>
            </div>
          )}
        </div>
        <SectorTrendChart data={sectorTrendData} dark={c.dark} />
        <LeerwegenChart data={leerwegenData} dark={c.dark} />

        <SectionHeader title="Diplomering" subtitle="Gediplomeerden per jaar, vergeleken met de regio" />
        <DiplomeringKpis {...c} rendement={c.rendement} />
        <BenchmarkLineChart title="Eerstejaars instroom per jaar"
          subtitle={`% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`}
          data={c.ejLineData} indexOpts={c.indexOpts} />
        <BenchmarkLineChart title="Gediplomeerden per jaar" subtitle={`% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.diplLineData} indexOpts={c.indexOpts} />
        <RendementVergelijkingChart data={rendVergData} dark={c.dark} />

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://onderwijsdata.duo.nl/dataset/p04hogdipl" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Gediplomeerden HO per instelling (p04hogdipl)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}
