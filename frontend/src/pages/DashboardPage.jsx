import { useSearchParams } from 'react-router-dom'
import { BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL } from '../workbooks'
import { DEFAULT_INSTELLING } from '../constants'
import WorkbookViewer from '../components/WorkbookViewer'
import DashboardGallery from '../components/DashboardGallery'
import ConfirmModal from '../components/ConfirmModal'
import VerwijderFout from '../components/VerwijderFout'
import { useWorkbookGallery } from '../hooks/useWorkbookGallery'
import { useDocumentTitle, pageTitle } from '../hooks/useDocumentTitle'

const BUILTINS = [BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL]

// Een link naar een dashboard uit de dashboardbouwer (#765): die is uit de app gehaald, het dashboard zelf niet.
export const BOUWER_WEG =
  'Dit dashboard is gemaakt met de dashboardbouwer. Die is uit de app gehaald, dus openen kan niet meer. ' +
  'Het dashboard zelf is bewaard: het staat in de export van je gegevens, en hieronder kun je het verwijderen.'

// De drie vaste dashboards. Een opgeslagen dashboard uit de dashboardbouwer opent niet meer, maar staat in de lijst
// onder de vaste dashboards, zodat het nog los te verwijderen is (#765).
export default function DashboardPage({ settings, feedbackEnabled = false }) {
  useDocumentTitle(pageTitle('Dashboards'))
  const [searchParams, setSearchParams] = useSearchParams()
  const id = searchParams.get('id')
  const selected = BUILTINS.find(b => b.id === id) ?? null

  const { workbooks: opgeslagen, pendingConfirm, setPendingConfirm, handleDelete, verwijderFout } = useWorkbookGallery({
    type: 'dashboard',
    deleteMessage: 'Weet je zeker dat je dit dashboard wilt verwijderen?',
  })

  const instelling = settings?.instelling?.trim() || DEFAULT_INSTELLING

  if (selected) {
    return (
      <WorkbookViewer
        workbook={selected}
        instelling={instelling}
        gekozenInstelling={settings?.instelling?.trim() || ''}
        onBack={() => setSearchParams({}, { replace: true })}
        onUpdate={() => {}}
        backLabel="Dashboards"
        feedbackEnabled={feedbackEnabled}
      />
    )
  }

  return (
    <>
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
        workbooks={BUILTINS}
        opgeslagen={opgeslagen}
        instelling={instelling}
        onSelect={wb => setSearchParams({ id: wb.id }, { replace: true })}
        onDelete={handleDelete}
      />
    </>
  )
}
