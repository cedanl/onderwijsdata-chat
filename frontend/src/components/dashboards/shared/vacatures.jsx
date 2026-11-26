// De vacatures van de arbeidsmarktdashboards komen sinds #1225 uit CBS-tabel 83599NED: openstaande vacatures per
// kwartaal, per provincie en per bedrijfstak (een sectie van de SBI), licentie CC BY 4.0. Tot #1225 was dat UWV Open
// Match, een momentopname van mei 2023. Elk onderdeel dat de vacatures gebruikt, noemt bron en kwartaal uit de payload
// en zegt "voorlopig" waar CBS dat zegt; de frontend rekent niets zelf uit. De arbeidsmarktmatch zegt daarbij wat haar
// labels betekenen en wat ze niet zeggen; drempel, kwartalen, jaren en de koppeltabel komen uit `match_duiding`
// (data/dashboard.py, _match_duiding).

import { fmt } from './getal'
import { langeDatum } from './datum'

export const CBS_VACATURES = 'https://opendata.cbs.nl/#/CBS/nl/dataset/83599NED/table'
export const CBS_LICENTIE = 'CC BY 4.0'

// De ouderdom in woorden, met dezelfde regel als de backend (`ouderdom_tekst` in data/arbeidsmarkt.py): onder een maand
// "minder dan een maand", dan maanden, vanaf 12 maanden jaren met "ruim" als er maanden over zijn (42 → "ruim 3 jaar").
// Zonder ouderdom in de payload null.
export function ouderdomTekst(maanden) {
  if (maanden == null || !Number.isFinite(Number(maanden))) return null
  const m = Number(maanden)
  if (m < 1) return 'minder dan een maand'
  if (m < 12) return `${m} ${m === 1 ? 'maand' : 'maanden'}`
  return `${m % 12 ? 'ruim ' : ''}${Math.floor(m / 12)} jaar`
}

// "CBS 83599NED, 2026 3e kwartaal, voorlopig": voor ondertitels die de vacatures noemen. Zonder periode (CBS laadde
// niet) alleen de tabel.
export function cbsBron(periode, voorlopig) {
  return ['CBS 83599NED', periode, periode && voorlopig ? 'voorlopig' : null].filter(Boolean).join(', ')
}

// [2023, 2024, 2025] → "2023 tot en met 2025"; één jaar is dat jaar; geen jaren is null.
export function jarenTekst(jaren) {
  if (!jaren?.length) return null
  return jaren.length === 1 ? String(jaren[0]) : `${jaren[0]} tot en met ${jaren[jaren.length - 1]}`
}

function ExterneLink({ href, children }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" aria-label={`${children} (opent in een nieuw tabblad)`}>
      {children}
    </a>
  )
}

// De bronregel boven elk onderdeel met vacatures: tabel (met link), licentie en kwartaal, en "voorlopig" als CBS dat
// zegt. `gemiddelde`: de periode is een gemiddelde over meer kwartalen (de match). Is het laatste kwartaal meer dan 12
// maanden oud (zegt de payload), dan is de regel een waarschuwing, zoals tot #1225 bij de stand van UWV.
export function VacatureBron({ periode, voorlopig, gemiddelde = false, ouderdomMaanden, verouderd }) {
  const ouderdom = ouderdomTekst(ouderdomMaanden)
  return (
    <div className={verouderd ? 'db-vacaturebron db-momentopname--verouderd' : 'db-vacaturebron'} role="note">
      <p>
        Vacatures: <ExterneLink href={CBS_VACATURES}>CBS-tabel 83599NED</ExterneLink>, openstaande vacatures per
        bedrijfstak (licentie {CBS_LICENTIE}), {periode ? `${gemiddelde ? 'gemiddeld over ' : ''}${periode}` : 'periode onbekend'}.
        {periode && voorlopig && ' CBS noemt deze cijfers voorlopig: ze kunnen nog wijzigen.'}
      </p>
      {verouderd && ouderdom && (
        <p>
          <strong>Verouderd:</strong> het laatste kwartaal is {ouderdom} oud; CBS heeft de tabel sindsdien niet bijgewerkt.
        </p>
      )}
    </div>
  )
}

// Onder de aansluiting: bron en kwartalen, drempel, de drie labels en wat de indicatie niet zegt.
export function MatchDuiding({ duiding }) {
  if (!duiding) return null
  const vacatures = duiding.vacatures || {}
  const drempel = duiding.drempel != null ? fmt(duiding.drempel) : null
  const jaren = jarenTekst(duiding.diplomajaren)
  const kwartalen = vacatures.kwartalen ? `${vacatures.kwartalen} kwartalen` : 'meer kwartalen'
  const koppeltabel = duiding.koppeltabel || {}
  const bijgewerkt = koppeltabel.bijgewerkt ? `, bijgewerkt op ${langeDatum(koppeltabel.bijgewerkt)}` : ''
  const minimum = duiding.min_gediplomeerden != null ? fmt(duiding.min_gediplomeerden) : null
  const periode = vacatures.periode ? `gemiddelde ${vacatures.periode}` : null
  return (
    <div className="db-match-duiding dashboard-noot" role="note">
      <p>
        Per sector het aandeel in de vacatures van zijn bedrijfstakken ({cbsBron(periode, vacatures.voorlopig)}) tegenover het
        aandeel in de gediplomeerden van deze instelling (DUO, {jaren ? `gemiddeld over de diplomajaren ${jaren}` : 'gemiddeld per jaar'}).
        Beide aandelen gelden binnen de sectoren van deze instelling.
      </p>
      {drempel && (
        <ul>
          <li><strong>Schaarste</strong>: het vacature-aandeel is meer dan {drempel} keer het diploma-aandeel.</li>
          <li><strong>Overaanbod</strong>: het diploma-aandeel is meer dan {drempel} keer het vacature-aandeel.</li>
          <li><strong>Evenwicht</strong>: geen van beide aandelen is meer dan {drempel} keer het andere.</li>
        </ul>
      )}
      <p>
        {duiding.uitleg || 'De vacatures tellen per bedrijfstak, niet per beroep: het label per sector is indicatief.'}{' '}
        Teller en noemer verschillen: een gemiddelde voorraad vacatures over {kwartalen} in de hele provincie tegenover
        een jaarlijkse stroom diploma&apos;s van deze ene instelling; de verhouding zegt niet hoeveel vacatures er per
        gediplomeerde zijn. Een
        bedrijfstak die bij meer sectoren hoort, telt per sector naar rato mee. De koppeltabel van bedrijfstakken en
        sectoren is {koppeltabel.herkomst || 'een indeling van deze app'}{bijgewerkt}.
        {minimum && ` Een sector met minder dan ${minimum} gediplomeerden per jaar krijgt geen label: daar verschuift één diploma de verhouding te sterk.`}
      </p>
    </div>
  )
}
