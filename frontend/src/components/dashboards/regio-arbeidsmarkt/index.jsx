import {
  useRegioDashboardData, DashboardShell,
  useRegioComputed, RegioBadges,
  RoaSection, UwvSection, KaartSection,
} from '../shared/index'

export function InlineDashboardRegioArbeidsmarkt({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const c = useRegioComputed(data, instelling)

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={data?.provincie} arbeidsmarktregio={data?.arbeidsmarktregio} bron="UWV &amp; ROA" />

        <KaartSection figureJson={data?.kaart_figure_json} />

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
