import { useRef } from 'react'
import { BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL } from '../../workbooks'
import { useInBeeld, useMiniatuurSchaal, MINIATUUR_BREEDTE, MINIATUUR_HOOGTE } from '../../hooks/useMiniatuur'
import {
  useRegioDashboardData, useArbeidsmarktmatchDashboardData, useNationaalDashboardData,
  useRegioComputed, useDarkMode, SectionHeader,
} from './shared/index'
import { Kerncijfers } from './mijn-instelling/kerncijfers'
import { MatchScoreSection } from './arbeidsmarkt-consolidated/index'
import { PositieKpis } from './nationaal/index'

// De galerijkaart van een vast dashboard toont de echte bovenkant van dat dashboard (#933): dezelfde sectie, met de
// cijfers van de gekozen instelling, op een pagina van 960 px verkleind tot de kaart, zoals een rapportkaart (#633).
// Alleen een kaart op of vlak bij het scherm laadt, en de lading is die van het dashboard zelf (DashboardLadingen):
// openen na de miniatuur vraagt de server niets nieuws. Geen grafieken: een KPI-rij met sparklines is lichte SVG, een
// Chart.js- of Plotly-grafiek per kaart niet, en verkleind tot een derde zegt hij weinig. De kaart van Mijn instelling
// slaat daarom ook de landkaart (Plotly) boven de kerncijfers over.

// Een melding op kaartmaat, niet verkleind: in 155 px past geen foutbalk, en een lege witte kaart zegt niets.
function Melding({ children }) {
  return <p className="wb-miniatuur-melding">{children}</p>
}

function Bovenkant({ instelling, data, error, leeg, schaal, children }) {
  if (error) return <Melding>De cijfers konden nu niet worden geladen. Open het dashboard om het opnieuw te proberen.</Melding>
  if (!data) return <div className="wb-preview-shimmer" />
  if (!data.gevonden) return <Melding>&ldquo;{instelling}&rdquo; niet gevonden in DUO-data. Pas de naam aan via Instellingen.</Melding>
  if (leeg) return <Melding>Geen cijfers voor de bovenkant van dit dashboard. Open het dashboard voor de rest.</Melding>
  return (
    <div
      className="wb-preview-frame-outer wb-miniatuur-pagina"
      style={{ width: MINIATUUR_BREEDTE, transform: `scale(${schaal})`, height: Math.ceil(MINIATUUR_HOOGTE / schaal) }}
    >
      {children}
    </div>
  )
}

function MijnInstellingBoven({ instelling, schaal }) {
  const { data, error } = useRegioDashboardData(instelling)
  const c = useRegioComputed(data, instelling)
  return (
    <Bovenkant instelling={instelling} data={data} error={error} schaal={schaal} leeg={!c.lastInges && !c.lastEj && !c.lastDipl}>
      <Kerncijfers data={data} instelling={instelling} c={c} />
    </Bovenkant>
  )
}

function ArbeidsmarktBoven({ instelling, schaal }) {
  const { data, error } = useArbeidsmarktmatchDashboardData(instelling)
  const dark = useDarkMode()
  const leeg = !Object.values(data?.match_score || {}).some(v => v != null)
  return (
    <Bovenkant instelling={instelling} data={data} error={error} schaal={schaal} leeg={leeg}>
      <MatchScoreSection matchScore={data?.match_score} verhouding={data?.match_verhouding} duiding={data?.match_duiding} dark={dark} />
    </Bovenkant>
  )
}

function LandelijkBoven({ instelling, schaal }) {
  const { data, error } = useNationaalDashboardData(instelling)
  return (
    <Bovenkant instelling={instelling} data={data} error={error} schaal={schaal} leeg={!Object.keys(data?.eigen_positie || {}).length}>
      <SectionHeader title="Positie per sector" />
      <PositieKpis data={data} />
    </Bovenkant>
  )
}

const BOVENKANT = {
  [BUILTIN_MIJN_INSTELLING.id]: MijnInstellingBoven,
  [BUILTIN_ARBEIDSMARKT.id]: ArbeidsmarktBoven,
  [BUILTIN_NATIONAAL.id]: LandelijkBoven,
}

// Alleen om naar te kijken: de kaart eromheen is de link, met haar eigen naam. De uitsnede is verborgen voor
// hulpsoftware en inert (geen focus, geen klik), zodat haar kopjes en cijfers de kaart geen tweede naam of extra
// koppen geven.
export function DashboardMiniatuur({ wb, instelling }) {
  const ref = useRef(null)
  const inBeeld = useInBeeld(ref)
  const schaal = useMiniatuurSchaal(ref)
  const Boven = BOVENKANT[wb.id]
  return (
    <div ref={ref} className="wb-preview-wrap wb-miniatuur" aria-hidden="true" inert>
      {inBeeld && Boven ? <Boven instelling={instelling} schaal={schaal} /> : <div className="wb-preview-shimmer" />}
    </div>
  )
}
