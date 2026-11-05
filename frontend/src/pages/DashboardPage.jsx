import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL, mijnInstellingBeschrijving } from '../workbooks'
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
const BUILTINS = [BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL]

// Een link naar een dashboard uit de dashboardbouwer (#765): die is uit de app gehaald, het dashboard zelf niet.
export const BOUWER_WEG =
  'Dit dashboard is gemaakt met de dashboardbouwer. Die is uit de app gehaald, dus openen kan niet meer. ' +
  'Het dashboard zelf is bewaard: het staat in de export van je gegevens, en hieronder kun je het verwijderen.'

// De drie vaste dashboards. Een opgeslagen dashboard uit de dashboardbouwer opent niet meer, maar staat in de lijst
// onder de vaste dashboards, zodat het nog los te verwijderen is (#765).
export default function DashboardPage({ settings, instellingen = GEEN_INSTELLINGEN, feedbackEnabled = false }) {
  useDocumentTitle(pageTitle('Dashboards'))
  const [searchParams, setSearchParams] = useSearchParams()
  const id = searchParams.get('id')
  const selected = BUILTINS.find(b => b.id === id) ?? null

  const { workbooks: opgeslagen, pendingConfirm, setPendingConfirm, handleDelete, verwijderFout } = useWorkbookGallery({
    type: 'dashboard',
    deleteMessage: 'Weet je zeker dat je dit dashboard wilt verwijderen?',
  })

  const instelling = settings?.instelling?.trim() || DEFAULT_INSTELLING
  // De kaart van Mijn instelling belooft alleen wat het dashboard van dit niveau toont (#918).
  const dashboards = useMemo(() => {
    const sector = instellingType(instelling, instellingen)
    return BUILTINS.map(b => (b.id === BUILTIN_MIJN_INSTELLING.id ? { ...b, description: mijnInstellingBeschrijving(sector) } : b))
  }, [instelling, instellingen])

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
      {id && <div className="wb-gallery-notice" role="alert">{BOUWER_WEG}</div>}
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
