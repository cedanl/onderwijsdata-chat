import { useState } from 'react'
import { SECTOR_LABELS, darkColors, horizontalBarOpts, sectorKleuren, staafHoogte, tellingAs } from './chart-opts'
import { ChartCard } from './shell'
import { OndergrensCategorieen } from './ondergrens'
import { Grafiek } from './grafiek'
import { asJaar, jaarLabel } from '../../../schooljaar'
import { fmt } from './getal'

// ─── Sector trend & Leerweg trend ────────────────────────────────────────────

// `soort`: het soort jaar van de ingeschrevenen uit de payload (#904); de as toont een schooljaar als 2025/26.
export function buildSectorTrendData(sectorenTrend, soort) {
  if (!sectorenTrend || Object.keys(sectorenTrend).length === 0) return null
  const sectors = Object.keys(sectorenTrend)
  const allJaren = [...new Set(sectors.flatMap(s => Object.keys(sectorenTrend[s]).map(String)))]
    .sort((a, b) => a - b)
  if (allJaren.length < 2) return null
  const kleuren = sectorKleuren(sectors)
  return {
    labels: allJaren.map(j => asJaar(j, soort)),
    datasets: sectors.map(sector => ({
      label: SECTOR_LABELS[sector] || sector,
      // Een jaar zonder waarde blijft een gat, geen val naar 0 (#902).
      data: allJaren.map(j => sectorenTrend[sector][j] ?? sectorenTrend[sector][Number(j)] ?? null),
      backgroundColor: kleuren.get(sector) + 'BB',
      borderColor: kleuren.get(sector),
      borderWidth: 1,
      fill: true,
    })),
  }
}

// De vier leerwegen van mbo-studenten-per-instelling: samen het totaal ingeschrevenen, Extraneus inbegrepen (#899).
export const LEERWEGEN_MBO = ['BBL', 'BOL voltijd', 'BOL deeltijd', 'Extraneus']

export function buildLeerwegenData(leerwegen, soort) {
  if (!leerwegen || Object.keys(leerwegen).length < 2) return null
  const jaren = Object.keys(leerwegen).sort((a, b) => a - b)
  const tracks = LEERWEGEN_MBO
  const kleuren = sectorKleuren(tracks)
  // Guard: require at least one year with BBL/BOL data
  const hasBblBol = jaren.some(j => tracks.some(t => leerwegen[j]?.[t] > 0))
  if (!hasBblBol) return null
  return {
    labels: jaren.map(j => asJaar(j, soort)),
    datasets: tracks.map(track => ({
      label: track,
      data: jaren.map(j => leerwegen[j]?.[track] ?? null),
      backgroundColor: kleuren.get(track) + 'CC',
      borderColor: kleuren.get(track),
      borderWidth: 1,
      fill: true,
    })),
  }
}

// Het aandeel per jaar over de reeksen met een waarde; een gat blijft een gat (#902).
function _normalizeProportional(data) {
  const totals = data.labels.map((_, i) =>
    data.datasets.reduce((sum, ds) => (ds.data[i] == null ? sum : sum + ds.data[i]), 0)
  )
  return {
    ...data,
    datasets: data.datasets.map(ds => ({
      ...ds,
      data: ds.data.map((v, i) => (v != null && totals[i] > 0 ? Math.round((v / totals[i]) * 1000) / 10 : null)),
    })),
  }
}

function _stackedAreaOpts(dark, proportional = false) {
  const { tick, grid, label } = darkColors(dark)
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true, position: 'top',
        labels: { color: label, boxWidth: 14 },
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        ...(proportional ? { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.raw)}%` } } : {}),
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: tick }, stacked: true },
      y: tellingAs({
        grid: { color: grid },
        ticks: { color: tick, ...(proportional ? { callback: v => `${fmt(v)}%` } : {}) },
        stacked: true,
        ...(proportional ? { min: 0, max: 100 } : {}),
      }),
    },
  }
}

// Aantallen of aandelen (#905): een schakelknop met een vaste naam en aria-pressed, zodat een schermlezer zegt wat hij
// doet en of hij aan staat; groot genoeg om te raken (.db-schakel).
function AandeelKnop({ aan, onWissel }) {
  return (
    <button type="button" className="db-schakel" aria-pressed={aan} onClick={onWissel}>
      Toon als %
    </button>
  )
}

export function SectorTrendChart({ data, dark }) {
  const [proportional, setProportional] = useState(false)
  if (!data) return null
  const displayData = proportional ? _normalizeProportional(data) : data
  return (
    <ChartCard
      title="Inschrijvingen per sector over tijd"
      subtitle="Stacked — welke faculteiten groeien of krimpen?"
      actions={<AandeelKnop aan={proportional} onWissel={() => setProportional(p => !p)} />}
    >
      <Grafiek soort="line" data={displayData} options={_stackedAreaOpts(dark, proportional)} hoogte={260} />
    </ChartCard>
  )
}

// Ingeschrevenen per DUO-hoofdgroep: TOTAAL MBO telt wie ingeschreven staat, nieuw of niet; geen eerstejaars en geen
// gediplomeerden (domeinregel mbo-instroom-totaal-mbo, #899). Het bestand is een ander dan dat van het totaal. Het jaar
// staat niet in het bestand: het payload geeft het mee (#934).
export function HoofdgroepenChart({ perHoofdgroep, jaar, soort, onderdrukt, dark }) {
  if (!perHoofdgroep || Object.keys(perHoofdgroep).length === 0) return null
  const entries = Object.entries(perHoofdgroep).sort((a, b) => b[1] - a[1])
  const h = staafHoogte(entries.map(([k]) => k), { perRij: 36 })
  const kleuren = sectorKleuren(entries.map(([k]) => k))
  const inJaar = jaar ? ` in ${jaarLabel(jaar, soort)}` : ''
  return (
    <ChartCard
      title="Ingeschrevenen per hoofdgroep"
      subtitle={`Mbo-studenten per DUO-hoofdgroep${inJaar}, ingeschreven op 1 oktober (DUO instromende-mbo-studenten, TOTAAL MBO). Geen eerstejaars: nieuw of niet. Een ander DUO-bestand dan het totaal ingeschrevenen, dus de som wijkt daarvan af.`}
    >
      <Grafiek
        soort="bar"
        hoogte={h}
        categorie="Hoofdgroep"
        data={{
          labels: entries.map(([k]) => k),
          datasets: [{
            label: 'Ingeschrevenen',
            data: entries.map(([, v]) => v),
            backgroundColor: entries.map(([k]) => kleuren.get(k)),
            borderWidth: 0,
            borderRadius: 4,
          }],
        }}
        options={horizontalBarOpts(dark)}
      />
      <OndergrensCategorieen onderdrukt={onderdrukt} />
    </ChartCard>
  )
}

export function LeerwegenChart({ data, dark }) {
  const [proportional, setProportional] = useState(false)
  if (!data) return null
  const displayData = proportional ? _normalizeProportional(data) : data
  return (
    <ChartCard
      title="Leerweg-verdeling over tijd"
      subtitle="Ingeschrevenen per leerweg per jaar: BBL, BOL voltijd, BOL deeltijd en Extraneus, samen het totaal ingeschrevenen"
      actions={<AandeelKnop aan={proportional} onWissel={() => setProportional(p => !p)} />}
    >
      <Grafiek soort="line" data={displayData} options={_stackedAreaOpts(dark, proportional)} hoogte={260} />
    </ChartCard>
  )
}
