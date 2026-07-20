import { CHART_COLORS } from '../constants'
import { Bar, Doughnut } from 'react-chartjs-2'
import {
  useDarkMode, chartOpts, doughnutOpts,
  useRegioDashboardData, DashboardShell,
  buildBarChartData, buildSectorChartData,
  useRegioComputed, SectionHeader, RegioBadges,
  DemografieKpis, InstroomKpis, DiplomeringKpis,
  RoaSection, UwvSection, BenchmarkLineChart,
} from './dashboard-shared'

// @deprecated Backward-compat voor gebruikers met __builtin_regio__ in localStorage.
// Verwijder na v1.8 zodra alle clients de gesplitste dashboards zien.
export function InlineDashboardRegio({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const c = useRegioComputed(data, instelling)

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={data?.provincie} bron="DUO Open Onderwijsdata" />

        <SectionHeader title="Demografie" subtitle="Potentiële lerenden en onderwijsprofessionals in de regio" />
        <DemografieKpis {...c} nInstellingen={c.bm.n_instellingen} laatsteJaar={data?.laatste_jaar} />
        <BenchmarkLineChart title="Ingeschrevenen per jaar" subtitle={`% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.ingesLineData} indexOpts={c.indexOpts} />

        <SectionHeader title="Instroom" subtitle="Eerstejaars aanmeldingen per jaar, vergeleken met de provincie" />
        <InstroomKpis {...c} />
        <BenchmarkLineChart title="Eerstejaars instroom per jaar" subtitle={`% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.ejLineData} indexOpts={c.indexOpts} />

        <SectionHeader title="Voortgang" subtitle="Inschrijvingen en sectoren per onderdeel" />
        <div className="charts-grid">
          {c.sectorData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Verdeling per sector {data.laatste_jaar}</div><div className="chart-sub">Ingeschrevenen naar onderdeel</div></div></div>
              <div style={{ height: 200 }}><Doughnut data={c.sectorData} options={doughnutOpts(c.dark)} /></div>
            </div>
          )}
          {c.ingesLineData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Inschrijvingen trend</div><div className="chart-sub">{instelling} (alle jaren)</div></div></div>
              <div style={{ height: 200 }}><Bar data={buildBarChartData(data?.ingeschrevenen, 'Ingeschrevenen', CHART_COLORS[0])} options={c.opts} /></div>
            </div>
          )}
        </div>

        <SectionHeader title="Diplomering" subtitle="Gediplomeerden per jaar, vergeleken met de provincie" />
        <DiplomeringKpis {...c} />
        <BenchmarkLineChart title="Gediplomeerden per jaar" subtitle={`% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.diplLineData} indexOpts={c.indexOpts} />

        <RoaSection data={data} />
        <UwvSection data={data} provincie={data?.provincie} dark={c.dark} opts={c.opts} />

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://onderwijsdata.duo.nl/dataset/p01hoinges" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Ingeschrevenen HO per instelling (p01hoinges)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/dataset/p02ho1ejrs" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Eerstejaars HO per instelling (p02ho1ejrs)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/dataset/p04hogdipl" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Gediplomeerden HO per instelling (p04hogdipl)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/dataset/mbo-studenten-per-instelling" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — MBO studenten per instelling</a></li>
            <li><a href="https://data.overheid.nl/dataset/uwv-open-match-data" target="_blank" rel="noreferrer">UWV Open Match — Vacaturedata per provincie en beroepscluster (mei 2023)</a></li>
            <li><a href="https://doi.org/10.34894/DVQTOG" target="_blank" rel="noreferrer">ROA — Arbeidsmarktinformatiesysteem (AIS), Schoolverlatersinformatie 2024 (nationaal gemiddelde)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}

export function InlineDashboardRegioInstroom({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const c = useRegioComputed(data, instelling)

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={data?.provincie} bron="DUO Open Onderwijsdata" />

        <SectionHeader title="Demografie" subtitle="Potentiële lerenden en onderwijsprofessionals in de regio" />
        <DemografieKpis {...c} nInstellingen={c.bm.n_instellingen} laatsteJaar={data?.laatste_jaar} />
        <BenchmarkLineChart title="Ingeschrevenen per jaar" subtitle={`% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.ingesLineData} indexOpts={c.indexOpts} />

        <SectionHeader title="Instroom" subtitle="Eerstejaars aanmeldingen per jaar, vergeleken met de provincie" />
        <InstroomKpis {...c} />
        <BenchmarkLineChart title="Eerstejaars instroom per jaar" subtitle={`% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.ejLineData} indexOpts={c.indexOpts} />
        {c.sectorData && (
          <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Verdeling per sector {data.laatste_jaar}</div><div className="chart-sub">Ingeschrevenen naar onderdeel</div></div></div>
              <div style={{ height: 200 }}><Doughnut data={c.sectorData} options={doughnutOpts(c.dark)} /></div>
            </div>
          </div>
        )}

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://onderwijsdata.duo.nl/dataset/p01hoinges" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Ingeschrevenen HO per instelling (p01hoinges)</a></li>
            <li><a href="https://onderwijsdata.duo.nl/dataset/p02ho1ejrs" target="_blank" rel="noreferrer">DUO Open Onderwijsdata — Eerstejaars HO per instelling (p02ho1ejrs)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}

export function InlineDashboardRegioDiplomering({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const c = useRegioComputed(data, instelling)

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={data?.provincie} bron="DUO Open Onderwijsdata" />

        <SectionHeader title="Voortgang" subtitle="Inschrijvingen en sectoren per onderdeel" />
        <div className="charts-grid">
          {c.sectorData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Verdeling per sector {data.laatste_jaar}</div><div className="chart-sub">Ingeschrevenen naar onderdeel</div></div></div>
              <div style={{ height: 200 }}><Doughnut data={c.sectorData} options={doughnutOpts(c.dark)} /></div>
            </div>
          )}
          {data?.ingeschrevenen && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Inschrijvingen trend</div><div className="chart-sub">{instelling} (alle jaren)</div></div></div>
              <div style={{ height: 200 }}><Bar data={buildBarChartData(data?.ingeschrevenen, 'Ingeschrevenen', CHART_COLORS[0])} options={c.opts} /></div>
            </div>
          )}
        </div>

        <SectionHeader title="Diplomering" subtitle="Gediplomeerden per jaar, vergeleken met de provincie" />
        <DiplomeringKpis {...c} />
        <BenchmarkLineChart title="Gediplomeerden per jaar" subtitle={`% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.diplLineData} indexOpts={c.indexOpts} />

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

export function InlineDashboardRegioArbeidsmarkt({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const c = useRegioComputed(data, instelling)

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={data?.provincie} bron="UWV &amp; ROA" />

        <RoaSection data={data} />
        <UwvSection data={data} provincie={data?.provincie} dark={c.dark} opts={c.opts} />

        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://data.overheid.nl/dataset/uwv-open-match-data" target="_blank" rel="noreferrer">UWV Open Match — Vacaturedata per provincie en beroepscluster (mei 2023)</a></li>
            <li><a href="https://doi.org/10.34894/DVQTOG" target="_blank" rel="noreferrer">ROA — Arbeidsmarktinformatiesysteem (AIS), Schoolverlatersinformatie 2024 (nationaal gemiddelde)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}
