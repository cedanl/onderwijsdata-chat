import {
  useRegioDashboardData, DashboardShell,
  buildMarktaandeelData, buildGroeiRankingData,
  buildMarktaandeelTrendData, buildInstroomRatioData,
  buildSectorTrendData, buildLeerwegenData,
  useRegioComputed, SectionHeader, RegioBadges,
  DemografieKpis, InstroomKpis,
  BenchmarkLineChart, PeerLinesChart,
  MarktaandeelChart, GroeiRankingChart, KaartSection,
  MarktaandeelTrendChart, InstroomRatioChart,
  PeersTable, SectorTrendChart, LeerwegenChart,
} from '../shared/index'

export function InlineDashboardRegioInstroom({ instelling }) {
  const { data, loading, error } = useRegioDashboardData(instelling)
  const c = useRegioComputed(data, instelling)
  const marktData = buildMarktaandeelData(data, instelling, c.dark)
  const marktTrendData = buildMarktaandeelTrendData(data)
  const groeiData = buildGroeiRankingData(data, instelling, c.dark)
  const ratioData = buildInstroomRatioData(data)
  const sectorTrendData = buildSectorTrendData(data?.sectoren_trend)
  const leerwegenData = buildLeerwegenData(data?.leerwegen)

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={data?.provincie} arbeidsmarktregio={data?.arbeidsmarktregio} bron="DUO Open Onderwijsdata" />

        <KaartSection figureJson={data?.kaart_figure_json} />

        <SectionHeader title="Demografie" subtitle="Potentiële lerenden en onderwijsprofessionals in de regio" />
        <DemografieKpis {...c} nInstellingen={c.bm.n_instellingen} laatsteJaar={data?.laatste_jaar} />
        <PeersTable data={data} instelling={instelling} />
        <PeerLinesChart
          title="Ingeschrevenen per jaar"
          subtitle={c.hasPeers ? `% verandering t.o.v. eerste jaar — ${instelling} (dik) vs. concurrenten in de regio` : `% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`}
          data={c.ingesLineData}
          opts={c.hasPeers ? c.peerOpts : c.indexOpts}
        />
        <MarktaandeelChart data={marktData} jaar={data?.laatste_jaar} dark={c.dark} />
        <MarktaandeelTrendChart data={marktTrendData} dark={c.dark} />
        <GroeiRankingChart data={groeiData} dark={c.dark} />

        <SectionHeader title="Instroom" subtitle="Eerstejaars aanmeldingen per jaar, vergeleken met de regio" />
        <InstroomKpis {...c} />
        <BenchmarkLineChart title="Eerstejaars instroom per jaar" subtitle={`% verandering t.o.v. eerste jaar — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.ejLineData} indexOpts={c.indexOpts} />
        <InstroomRatioChart data={ratioData} dark={c.dark} />
        <SectorTrendChart data={sectorTrendData} dark={c.dark} />
        <LeerwegenChart data={leerwegenData} dark={c.dark} />

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
