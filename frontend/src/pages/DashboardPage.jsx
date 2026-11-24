import { useEffect, useMemo, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL, BUILTIN_OPLEIDINGEN, mijnInstellingBeschrijving,
  opleidingenBeschrijving,
} from '../workbooks'
import { instellingType } from '../instellingenMatch'
import { DEFAULT_INSTELLING } from '../constants'
import WorkbookViewer from '../components/WorkbookViewer'
import DashboardGallery from '../components/DashboardGallery'
import { DashboardLadingen } from '../components/dashboards/shared/hooks'
import ConfirmModal from '../components/ConfirmModal'
import VerwijderFout from '../components/VerwijderFout'
import { useWorkbookGallery } from '../hooks/useWorkbookGallery'
import { useDocumentTitle, pageTitle } from '../hooks/useDocumentTitle'
import { focusEerste, kiezerMetId } from '../focusNa'

const GEEN_INSTELLINGEN = []
const GEEN_BRONNEN = {}
const VASTE = [BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL]

// Opleidingen (#957) staat er alleen waar de Studiekeuzedatabase antwoord geeft: `bronnen.studiekeuze` van /api/config,
// dezelfde regel als de tool en het eindpunt (tools/beschikbaarheid.py).
const MET_OPLEIDINGEN = [...VASTE, BUILTIN_OPLEIDINGEN]
export const vasteDashboards = bronnen => (bronnen?.studiekeuze ? MET_OPLEIDINGEN : VASTE)

export const OPLEIDINGEN_NIET_HIER =
  'Het dashboard Opleidingen is hier niet beschikbaar: de Studiekeuzedatabase van LCSK staat in deze omgeving niet aan.'

// Een link naar een dashboard uit de dashboardbouwer (#765): die is uit de app gehaald, het dashboard zelf niet.
export const BOUWER_WEG =
  'Dit dashboard is gemaakt met de dashboardbouwer. Die is uit de app gehaald, dus openen kan niet meer. ' +
  'Het dashboard zelf is bewaard: het staat in de export van je gegevens, en hieronder kun je het verwijderen.'

// Een gedeelde link draagt de instelling (#1071): `?instelling=` gaat voor het profiel, dat weer voor de standaard.
// Alleen voor de weergave; het opgeslagen profiel verandert niet. Vrije tekst uit een URL, dus begrensd.
export const MAX_URL_INSTELLING = 200
export function effectieveInstelling(urlInstelling, profielInstelling) {
  const uitUrl = urlInstelling?.trim().slice(0, MAX_URL_INSTELLING).trim()
  return uitUrl || profielInstelling?.trim() || DEFAULT_INSTELLING
}

// Zonder instelling in de link en zonder profiel tonen de dashboards de voorbeeldinstelling (#1098): dat moet erbij staan.
export const isVoorbeeldInstelling = (urlInstelling, profielInstelling) => !urlInstelling?.trim() && !profielInstelling?.trim()

// De vaste dashboards. Een opgeslagen dashboard uit de dashboardbouwer opent niet meer, maar staat in de lijst
// onder de vaste dashboards, zodat het nog los te verwijderen is (#765).
export default function DashboardPage({ settings, instellingen = GEEN_INSTELLINGEN, bronnen = GEEN_BRONNEN, feedbackEnabled = false, onOpenSettings = null }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const id = searchParams.get('id')
  const builtins = vasteDashboards(bronnen)
  const selected = builtins.find(b => b.id === id) ?? null
  // Het tabblad noemt het dashboard dat open is (#1173), zoals bij een rapport.
  useDocumentTitle(pageTitle(selected?.title ?? 'Dashboards'))

  const { workbooks: opgeslagen, pendingConfirm, setPendingConfirm, handleDelete, verwijderFout } = useWorkbookGallery({
    type: 'dashboard',
    deleteMessage: 'Weet je zeker dat je dit dashboard wilt verwijderen?',
  })

  const instelling = effectieveInstelling(searchParams.get('instelling'), settings?.instelling)
  const voorbeeld = isVoorbeeldInstelling(searchParams.get('instelling'), settings?.instelling)
  // Het niveau (mbo, hbo, wo) uit de lijst van /api/instellingen, of null voor vrije tekst die er niet in staat.
  const sector = useMemo(() => instellingType(instelling, instellingen), [instelling, instellingen])
  // De kaarten van Mijn instelling en Opleidingen beloven alleen wat het dashboard van dit niveau toont (#918, #957).
  const dashboards = useMemo(() => {
    const beschrijving = { [BUILTIN_MIJN_INSTELLING.id]: mijnInstellingBeschrijving, [BUILTIN_OPLEIDINGEN.id]: opleidingenBeschrijving }
    return builtins.map(b => (beschrijving[b.id] ? { ...b, description: beschrijving[b.id](sector) } : b))
  }, [builtins, sector])

  // Openen en terugkeren verwijderen het element met de focus; de focus gaat dan naar de kop van het dashboard
  // of naar de kaart die open was (#1172). Alleen na een keuze van de gebruiker, een link naar een dashboard
  // laat de focus waar de browser hem zet.
  const focusNaWissel = useRef(null)
  useEffect(() => {
    if (!focusNaWissel.current) return
    focusEerste(focusNaWissel.current)
    focusNaWissel.current = null
  }, [selected?.id])
  const open = wb => {
    focusNaWissel.current = '.wb-viewer-heading'
    setSearchParams({ id: wb.id, instelling }, { replace: true })
  }
  const terug = () => {
    focusNaWissel.current = kiezerMetId('.wb-card', 'data-wb-id', selected.id)
    setSearchParams({}, { replace: true })
  }

  // De galerij en het dashboard delen hun ladingen (#933): de miniatuur van een kaart en het dashboard erachter
  // vragen de server één keer. Beide takken beginnen met dezelfde provider, dus React houdt hem (en wat hij bewaart)
  // vast bij openen en teruggaan.
  if (selected) {
    return (
      <DashboardLadingen>
        <WorkbookViewer
          workbook={selected}
          instelling={instelling}
          sector={sector}
          gekozenInstelling={settings?.instelling?.trim() || ''}
          voorbeeld={voorbeeld}
          onKiesInstelling={onOpenSettings}
          onBack={terug}
          onUpdate={() => {}}
          backLabel="Dashboards"
          feedbackEnabled={feedbackEnabled}
        />
      </DashboardLadingen>
    )
  }

  return (
    <DashboardLadingen>
      {pendingConfirm && (
        <ConfirmModal
          message={pendingConfirm.message}
          onConfirm={() => { pendingConfirm.onConfirm(); setPendingConfirm(null) }}
          onCancel={() => setPendingConfirm(null)}
        />
      )}
      {id && <div className="wb-gallery-notice" role="alert">{id === BUILTIN_OPLEIDINGEN.id ? OPLEIDINGEN_NIET_HIER : BOUWER_WEG}</div>}
      <VerwijderFout fout={verwijderFout} />
      <DashboardGallery
        workbooks={dashboards}
        opgeslagen={opgeslagen}
        instelling={instelling}
        voorbeeld={voorbeeld}
        onKiesInstelling={onOpenSettings}
        onSelect={open}
        onDelete={handleDelete}
      />
    </DashboardLadingen>
  )
}
