import { useMemo } from 'react'
import {
  useRegioDashboardData, useRendementDashboardData,
  DashboardShell, SectionHeader, RegioBadges, DashboardSources, KaartSection,
  bronnenVan, bronBadge,
  useRegioComputed, useDarkMode,
  buildMarktaandeelData, buildGroeiRankingData,
  buildMarktaandeelTrendData, buildInstroomRatioData,
  buildSectorTrendData, buildLeerwegenData, buildRendementVergelijkingData,
  DemografieKpis, InstroomKpis, DiplomeringKpis, gediplomeerdenNoot, diplomaRatio, SECTOR_LABELS,
  BenchmarkLineChart, PeerLinesChart,
  MarktaandeelChart, GroeiRankingChart,
  MarktaandeelTrendChart, InstroomRatioChart,
  PeersTable, SectorTrendChart, LeerwegenChart, HoofdgroepenChart,
  RendementVergelijkingChart, NietGeladen, DeelLading, gatenVan,
  perJaar, OndergrensNoot,
} from '../shared/index'
import { useFinancienDashboardData, usePersoneelDashboardData } from '../shared/hooks'
import { jaarLabel } from '../../../schooljaar'
import { useBronAan } from '../../../bronnenAan'

// Van /api/dashboard/regio toont dit dashboard de DUO-onderdelen en -bronnen; UWV en ROA staan op het arbeidsmarktdashboard.
// UNL is WOPI, van het personeel (#936).
const REGIO_BRONNEN = ['DUO', 'UNL']
import { RendementSection } from './rendement-section'
import { GenderSection } from './gender-section'
import { Kerncijfers } from './kerncijfers'
import { FinancienSection } from './financien-section'
import { PersoneelSection } from './personeel-section'

// `sector`: het niveau van de instelling uit /api/instellingen (DashboardPage), of null als de lijst haar niet kent.
export function InlineDashboardMijnInstelling({ instelling, sector = null }) {
  const { data, loading, error, opnieuw } = useRegioDashboardData(instelling)
  const rendement = useRendementDashboardData(instelling)
  const rendData = rendement.data
  // De financiën en het personeel alleen waar hun bron hier antwoord geeft (/api/config, #935, #936): anders bestaat
  // het eindpunt niet en vraagt de pagina niets op.
  const financienAan = useBronAan('financien')
  // Het personeel bestaat alleen voor wo (#973): bij een bekende hogeschool of mbo-instelling geen verzoek en geen
  // laadvlak. Kent de lijst de instelling niet, dan beslist de server, en verdwijnt de kaart na het antwoord.
  const personeelAan = useBronAan('wo_personeel') && (sector == null || sector === 'wo')
  const financien = useFinancienDashboardData(financienAan ? instelling : null)
  const personeel = usePersoneelDashboardData(personeelAan ? instelling : null)
  const ladingen = [data, rendData, financien.data, personeel.data]
  const gaten = gatenVan(ladingen, REGIO_BRONNEN)
  const bronnen = bronnenVan(ladingen, REGIO_BRONNEN)
  const allesOpnieuw = () => { opnieuw(); rendement.opnieuw(); financien.opnieuw(); personeel.opnieuw() }
  const c = useRegioComputed(data, instelling)
  const dark = useDarkMode()

  const {
    marktData, marktTrendData, groeiData, ratioData, sectorTrendData, leerwegenData, rendVergData, ratio,
  } = useMemo(() => ({
    marktData: buildMarktaandeelData(data, instelling, c.dark),
    marktTrendData: buildMarktaandeelTrendData(data),
    groeiData: buildGroeiRankingData(data, instelling, c.dark),
    ratioData: buildInstroomRatioData(data),
    sectorTrendData: buildSectorTrendData(data?.sectoren_trend, data?.perioden?.ingeschrevenen),
    leerwegenData: buildLeerwegenData(data?.leerwegen, data?.perioden?.ingeschrevenen),
    rendVergData: buildRendementVergelijkingData(data, instelling, c.dark),
    ratio: diplomaRatio(data),
  }), [data, instelling, c.dark])

  const bm = c.bm || {}
  // Onderdrukte cellen per reeks en jaar (#902): een getal daarover is "ten minste".
  const od = data?.onderdrukt || {}
  const bmOd = bm.onderdrukt || {}
  // Loopt de diplomareeks achter op de ingeschrevenen (hbo/wo), dan zegt de pagina tot wanneer DUO publiceert (#927).
  const { perioden } = c
  const diplNoot = gediplomeerdenNoot({ diplJaar: c.lastDipl?.[0], ingesJaar: c.lastInges?.[0], perioden })
  // Het startjaar van de groei als schooljaar of diplomajaar, naar de reeks (#904).
  const vanaf = sleutel => startjaar => (startjaar != null ? `% verandering t.o.v. ${jaarLabel(startjaar, perioden[sleutel])}` : '% verandering')
  const noot = (sleutel, label) => [
    { label, onderdrukt: od[sleutel], soort: perioden[sleutel] },
    { label: `${label} ${c.bmZin}`, onderdrukt: bmOd[sleutel], soort: perioden[sleutel] },
  ]
  const sectorNoot = Object.entries(od.sectoren_trend || {}).map(([s, onderdrukt]) => ({ label: SECTOR_LABELS[s] || s, onderdrukt, soort: perioden.ingeschrevenen }))
  // Een grafiek belooft de vergelijking met het gemiddelde alleen als dat er is (#951: bij het mbo stond bij
  // "Gediplomeerden per jaar" alleen de eigen lijn).
  const tegen = sleutel => (bm[sleutel] && Object.keys(bm[sleutel]).length ? `eigen instelling vs. ${c.bmZin}` : 'eigen instelling; geen gemiddelde van de vergelijkingsgroep')

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error} onOpnieuw={opnieuw}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <RegioBadges instelling={instelling} provincie={data?.provincie} herkomst={data?.provincie_herkomst} arbeidsmarktregio={data?.arbeidsmarktregio} bron={bronBadge(bronnen)} />
        <NietGeladen onderdelen={gaten} onOpnieuw={allesOpnieuw} />

        <KaartSection figureJson={data?.kaart_figure_json} />

        {/* ── Kerncijfers ── */}
        <Kerncijfers data={data} instelling={instelling} c={c} />

        {/* ── Instroom & demografie ── */}
        <SectionHeader title="Instroom & demografie" subtitle="Ingeschrevenen, eerstejaars en regionale vergelijking" />
        <DemografieKpis
          {...c}
          instelling={instelling}
          regioType={bm.regio_type}
          populatie={bm.populatie}
          nPeers={perJaar(bm.n_per_jaar?.ingeschrevenen, c.totaalRegioJaar) ?? bm.n_instellingen}
          laatsteJaar={data?.laatste_jaar}
          onderdrukt={od.ingeschrevenen}
          bmOnderdrukt={bmOd.ingeschrevenen}
        />
        <OndergrensNoot reeksen={noot('ingeschrevenen', 'Ingeschrevenen')} />
        <PeersTable data={data} instelling={instelling} dark={c.dark} />
        <PeerLinesChart
          title="Ingeschrevenen per jaar"
          subtitle={start => (c.hasPeers ? `${vanaf('ingeschrevenen')(start)} — ${instelling} (dik) vs. de andere ${bm.populatie}` : `${vanaf('ingeschrevenen')(start)} — eigen instelling vs. ${c.bmZin}`)}
          data={c.ingesLineData}
          opts={c.hasPeers ? c.peerOpts : c.indexOpts}
        />
        <InstroomKpis {...c} type={data?.type} />
        <OndergrensNoot reeksen={noot('eerstejaars', 'Eerstejaars')} />
        <BenchmarkLineChart title="Eerstejaars instroom per jaar" subtitle={start => `${vanaf('eerstejaars')(start)} — ${tegen('eerstejaars')}`} data={c.ejLineData} indexOpts={c.indexOpts} />
        <MarktaandeelChart data={marktData} dark={c.dark} />
        <MarktaandeelTrendChart data={marktTrendData} dark={c.dark} />
        <GroeiRankingChart data={groeiData} dark={c.dark} />
        <InstroomRatioChart data={ratioData} dark={c.dark} type={data?.type} />

        {/* ── Diplomering & rendement ── */}
        <SectionHeader title="Diplomering" subtitle="Gediplomeerden per jaar, vergeleken met de regio" />
        <DiplomeringKpis {...c} ratio={ratio} noot={diplNoot} />
        <OndergrensNoot reeksen={noot('gediplomeerden', 'Gediplomeerden')} />
        <BenchmarkLineChart title="Gediplomeerden per jaar" subtitle={start => `${vanaf('gediplomeerden')(start)} — ${tegen('gediplomeerden')}${diplNoot ? `. ${diplNoot}` : ''}`} data={c.diplLineData} indexOpts={c.indexOpts} />
        <RendementVergelijkingChart data={rendVergData} dark={c.dark} />

        <DeelLading titel="Diplomarendement" loading={rendement.loading} error={rendement.error} onOpnieuw={rendement.opnieuw} hoogte={320}>
          <RendementSection data={rendData} instelling={instelling} dark={dark} />
        </DeelLading>

        {/* ── Sectoren ── */}
        <SectionHeader title="Sectoren" subtitle="Verdeling en trend per onderdeel" />
        <SectorTrendChart data={sectorTrendData} dark={c.dark} />
        <LeerwegenChart data={leerwegenData} dark={c.dark} />
        <HoofdgroepenChart perHoofdgroep={data?.ingeschrevenen_per_hoofdgroep} jaar={data?.ingeschrevenen_per_hoofdgroep_jaar} soort={perioden.ingeschrevenen} onderdrukt={od.ingeschrevenen_per_hoofdgroep} dark={c.dark} />
        <OndergrensNoot reeksen={sectorNoot} />

        {/* ── Gender & diversiteit ── */}
        <GenderSection data={data} instelling={instelling} dark={dark} />

        {/* ── Bestuur en personeel ── */}
        {financienAan && (
          <DeelLading titel="Financiën van het bestuur" loading={financien.loading} error={financien.error} onOpnieuw={financien.opnieuw} hoogte={320}>
            <FinancienSection data={financien.data} dark={dark} />
          </DeelLading>
        )}
        {personeelAan && (
          <DeelLading titel="Personeel" loading={personeel.loading} error={personeel.error} onOpnieuw={personeel.opnieuw} hoogte={260}>
            <PersoneelSection data={personeel.data} dark={dark} />
          </DeelLading>
        )}

        <DashboardSources sources={bronnen} />
      </div>
    </DashboardShell>
  )
}
