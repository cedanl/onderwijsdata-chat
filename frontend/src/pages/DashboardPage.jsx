import { useMemo } from 'react'
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

// De vaste dashboards. Een opgeslagen dashboard uit de dashboardbouwer opent niet meer, maar staat in de lijst
// onder de vaste dashboards, zodat het nog los te verwijderen is (#765).
export default function DashboardPage({ settings, instellingen = GEEN_INSTELLINGEN, bronnen = GEEN_BRONNEN, feedbackEnabled = false }) {
  useDocumentTitle(pageTitle('Dashboards'))
  const [searchParams, setSearchParams] = useSearchParams()
  const id = searchParams.get('id')
  const builtins = vasteDashboards(bronnen)
  const selected = builtins.find(b => b.id === id) ?? null

  const { workbooks: opgeslagen, pendingConfirm, setPendingConfirm, handleDelete, verwijderFout } = useWorkbookGallery({
    type: 'dashboard',
    deleteMessage: 'Weet je zeker dat je dit dashboard wilt verwijderen?',
  })

  const instelling = settings?.instelling?.trim() || DEFAULT_INSTELLING
  // De kaarten van Mijn instelling en Opleidingen beloven alleen wat het dashboard van dit niveau toont (#918, #957).
  const dashboards = useMemo(() => {
    const sector = instellingType(instelling, instellingen)
    const beschrijving = { [BUILTIN_MIJN_INSTELLING.id]: mijnInstellingBeschrijving, [BUILTIN_OPLEIDINGEN.id]: opleidingenBeschrijving }
    return builtins.map(b => (beschrijving[b.id] ? { ...b, description: beschrijving[b.id](sector) } : b))
  }, [builtins, instelling, instellingen])

  // De galerij en het dashboard delen hun ladingen (#933): de miniatuur van een kaart en het dashboard erachter
  // vragen de server één keer. Beide takken beginnen met dezelfde provider, dus React houdt hem (en wat hij bewaart)
  // vast bij openen en teruggaan.
  if (selected) {
    return (
      <DashboardLadingen>
        <WorkbookViewer
          workbook={selected}
          instelling={instelling}
          gekozenInstelling={settings?.instelling?.trim() || ''}
          onBack={() => setSearchParams({}, { replace: true })}
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
        onSelect={wb => setSearchParams({ id: wb.id }, { replace: true })}
        onDelete={handleDelete}
      />
    </DashboardLadingen>
  )
}
