import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchBronActualiteit } from '../api'
import { useDocumentTitle, pageTitle } from '../hooks/useDocumentTitle'
import TabelScroll from '../components/TabelScroll'

// Hoe actueel elke bron is (#1266), uit /api/bronactualiteit (core/bronactualiteit_overzicht.py). De pagina rekent niets
// zelf uit: geen datum uit de frequentie, geen omgerekende datum. Wat de server niet weet, staat er als "onbekend". Een
// verwachte volgende editie staat er alleen met de bron die haar noemt; zonder die bron is ze "onbekend".
export const TITEL = 'Actualiteit van de bronnen'
export const ONBEKEND = 'onbekend'
const PER_DATASET = 'verschilt per dataset'

const tekst = waarde => (typeof waarde === 'string' && waarde.trim() ? waarde : ONBEKEND)
const isLink = url => typeof url === 'string' && /^https:\/\//i.test(url)

// Een datum zoals de bron hem geeft (jjjj-mm-dd), niet omgerekend: zo staat er nooit een andere dag dan in de bron.
function Datum({ waarde }) {
  const dag = tekst(waarde)
  return /^\d{4}-\d{2}-\d{2}$/.test(dag) ? <time dateTime={dag}>{dag}</time> : dag
}

function Status({ waarde }) {
  const status = tekst(waarde)
  const soort = status.includes('voorlopig') ? 'voorlopig' : status === 'definitief' ? 'definitief' : 'onbekend'
  return <span className={`bronact-status bronact-status--${soort}`}>{status}</span>
}

// De verwachte volgende editie met haar bron; zonder bron telt ze niet.
function Verwacht({ item }) {
  const verwacht = tekst(item.verwachte_volgende_editie)
  const bron = tekst(item.verwachte_volgende_editie_bron)
  if (verwacht === PER_DATASET) return PER_DATASET
  if (verwacht === ONBEKEND || bron === ONBEKEND) return ONBEKEND
  const url = item.verwachte_volgende_editie_url
  return (
    <>
      {verwacht}{' '}
      <span className="bronact-verwacht-bron">
        (bron: {isLink(url) ? <a href={url} target="_blank" rel="noreferrer">{bron}</a> : bron})
      </span>
    </>
  )
}

const BEREIKBAAR = {
  bereikbaar: 'ja, de bron antwoordt',
  'niet bereikbaar': 'nee, de bron antwoordt nu niet',
}

// De leeftijd van de UWV-stand, dezelfde tekst als op de dashboards en in de chat (#1219, ouderdom_tekst).
function Ouderdom({ ouderdom }) {
  const leeftijd = tekst(ouderdom?.tekst)
  if (leeftijd === ONBEKEND) return ONBEKEND
  return <>{leeftijd} oud{ouderdom.verouderd && <span className="bronact-verouderd"> (verouderd)</span>}</>
}

function Kern({ bron }) {
  const rijen = [
    ['Laatste periode of editie', tekst(bron.laatste_periode)],
    ['Laatste wijziging', <Datum key="d" waarde={bron.laatste_wijziging} />],
    ['Status', <Status key="s" waarde={bron.status} />],
    ['Frequentie', tekst(bron.frequentie)],
    ['Verwachte volgende editie', <Verwacht key="v" item={bron} />],
    ['Bereikbaar', BEREIKBAAR[bron.bereikbaar] || ONBEKEND],
    ...(bron.ouderdom ? [['Leeftijd van de stand', <Ouderdom key="o" ouderdom={bron.ouderdom} />]] : []),
  ]
  return (
    <dl className="bronact-kern">
      {rijen.map(([kop, waarde]) => (
        <div key={kop}><dt>{kop}</dt><dd>{waarde}</dd></div>
      ))}
    </dl>
  )
}

function Datasets({ bron }) {
  const datasets = Array.isArray(bron.datasets) ? bron.datasets : []
  if (!datasets.length) return null
  return (
    <details className="bronact-datasets">
      <summary>Per dataset ({datasets.length})</summary>
      <TabelScroll label={`Datasets van ${bron.naam}`} className="bronact-tabel">
        <thead>
          <tr>
            <th scope="col">Dataset</th>
            <th scope="col">Laatste periode of editie</th>
            <th scope="col">Laatste wijziging</th>
            <th scope="col">Status</th>
            <th scope="col">Frequentie</th>
            <th scope="col">Verwachte volgende editie</th>
          </tr>
        </thead>
        <tbody>
          {datasets.map(d => (
            <tr key={d.id}>
              <th scope="row">
                {isLink(d.url) ? <a href={d.url} target="_blank" rel="noreferrer">{tekst(d.titel)}</a> : tekst(d.titel)}
                <span className="bronact-id">{tekst(d.id)}</span>
              </th>
              <td>{tekst(d.laatste_periode)}</td>
              <td><Datum waarde={d.laatste_wijziging} /></td>
              <td><Status waarde={d.status} /></td>
              <td>{tekst(d.frequentie)}</td>
              <td><Verwacht item={d} /></td>
            </tr>
          ))}
        </tbody>
      </TabelScroll>
    </details>
  )
}

function Bron({ bron }) {
  const kop = `bronact-${bron.bron}`
  return (
    <section className="bronact-bron" aria-labelledby={kop}>
      <h2 id={kop}>{bron.naam} <span className="bronact-bron-titel">{bron.titel}</span></h2>
      {bron.melding && <p className="bronact-melding">{bron.melding}</p>}
      <Kern bron={bron} />
      <Datasets bron={bron} />
    </section>
  )
}

export default function BronActualiteitPage() {
  useDocumentTitle(pageTitle(TITEL))
  const [stand, setStand] = useState({ bronnen: null, fout: false })
  const laad = useCallback(() => {
    setStand({ bronnen: null, fout: false })
    fetchBronActualiteit()
      .then(data => setStand({ bronnen: Array.isArray(data?.bronnen) ? data.bronnen : [], fout: false }))
      .catch(() => setStand({ bronnen: null, fout: true }))
  }, [])
  useEffect(() => { laad() }, [laad])

  return (
    <article className="bronact-page">
      <h1>{TITEL}</h1>
      <p className="bronact-lead">
        Per bron en dataset: de laatste periode of editie, wanneer de bron haar het laatst wijzigde, of de cijfers
        voorlopig of definitief zijn en hoe vaak er nieuwe komen. Een verwachte volgende editie staat er alleen als de
        bron die zelf noemt, met die bron erbij. De app raadt geen datum. Wat niet bekend is, staat er als
        &ldquo;onbekend&rdquo;.
      </p>
      {stand.fout && (
        <div className="bronact-fout" role="alert">
          <p>De actualiteit van de bronnen kon niet worden opgehaald.</p>
          <button type="button" className="message-continue" onClick={laad}>Opnieuw proberen</button>
        </div>
      )}
      {!stand.fout && stand.bronnen === null && <p role="status">De actualiteit wordt geladen…</p>}
      {stand.bronnen?.map(bron => <Bron key={bron.bron} bron={bron} />)}
      <p className="bronact-voet">
        <Link to="/" className="notfound-link">Terug naar de startpagina</Link>
      </p>
    </article>
  )
}
