import { useMemo } from 'react'
import {
  useRegioDashboardData, useRendementDashboardData,
  DashboardShell, SectionHeader, RegioBadges, DashboardSources, KaartSection,
  BRONNEN_HO, BRONNEN_MBO,
  useRegioComputed, useDarkMode,
  buildMarktaandeelData, buildGroeiRankingData,
  buildMarktaandeelTrendData, buildInstroomRatioData,
  buildSectorTrendData, buildLeerwegenData, buildRendementVergelijkingData,
  DemografieKpis, InstroomKpis, DiplomeringKpis,
  BenchmarkLineChart, PeerLinesChart,
  MarktaandeelChart, GroeiRankingChart,
  MarktaandeelTrendChart, InstroomRatioChart,
  PeersTable, SectorTrendChart, LeerwegenChart, HoofdgroepenChart,
  RendementVergelijkingChart, NietGeladen, DeelLading, gatenVan,
  perJaar, OndergrensNoot,
} from '../shared/index'

// Van /api/dashboard/regio toont dit dashboard de DUO-onderdelen; UWV en ROA staan op het arbeidsmarktdashboard.
const REGIO_BRONNEN = ['DUO']
import { RendementSection } from './rendement-section'
import { GenderSection } from './gender-section'
import { Kerncijfers } from './kerncijfers'

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
        <Kerncijfers data={data} instelling={instelling} c={c} />

        {/* ── Instroom & demografie ── */}
        <SectionHeader title="Instroom & demografie" subtitle="Ingeschrevenen, eerstejaars en regionale vergelijking" />
        <DemografieKpis {...c} regioType={bm.regio_type} nInstellingen={perJaar(bm.n_per_jaar?.ingeschrevenen, c.totaalRegioJaar) ?? bm.n_instellingen} laatsteJaar={data?.laatste_jaar} />
        <OndergrensNoot reeksen={noot('ingeschrevenen', 'Ingeschrevenen')} />
        <PeersTable data={data} instelling={instelling} dark={c.dark} />
        <PeerLinesChart
          title="Ingeschrevenen per jaar"
          subtitle={start => (c.hasPeers ? `${vanaf(start)} — ${instelling} (dik) vs. concurrenten in de regio` : `${vanaf(start)} — eigen instelling vs. ${c.bmLabel.toLowerCase()}`)}
          data={c.ingesLineData}
          opts={c.hasPeers ? c.peerOpts : c.indexOpts}
        />
        <InstroomKpis {...c} type={data?.type} />
        <OndergrensNoot reeksen={noot('eerstejaars', 'Eerstejaars')} />
        <BenchmarkLineChart title="Eerstejaars instroom per jaar" subtitle={start => `${vanaf(start)} — eigen instelling vs. ${c.bmLabel.toLowerCase()}`} data={c.ejLineData} indexOpts={c.indexOpts} />
        <MarktaandeelChart data={marktData} jaar={data?.laatste_jaar} dark={c.dark} />
        <MarktaandeelTrendChart data={marktTrendData} dark={c.dark} />
        <GroeiRankingChart data={groeiData} dark={c.dark} />
        <InstroomRatioChart data={ratioData} dark={c.dark} type={data?.type} />

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
