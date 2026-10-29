import { useOnline } from '../hooks/useOnline'
import { connectionStatus, connectionStatusText, wachtOpGebruiker } from '../connectionStatus'

// The connection status in a composer footer (#532, WCAG 4.1.3). The live region is always mounted,
// empty while the connection is fine: a region mounted together with its text is often not announced.
// Once the hook stopped trying (#783), a button in the same line reconnects. It sits inside the region, so on a
// phone it stays with the status above the composer, and "Geen verbinding. Opnieuw verbinden" is read as one.
export default function ConnectionStatus({ connected, opgegeven = null, onOpnieuw }) {
  const status = connectionStatus({ online: useOnline(), connected, opgegeven })
  return (
    <span className="ws-reconnecting" role="status" aria-live="polite">
      {status !== 'ok' && (
        <>
          <span className={wachtOpGebruiker(status) ? 'ws-dot ws-dot--stil' : 'ws-dot'} aria-hidden="true" />
          {connectionStatusText(status)}
          {wachtOpGebruiker(status) && onOpnieuw && (
            <button type="button" className="ws-opnieuw" onClick={onOpnieuw}>Opnieuw verbinden</button>
          )}
        </>
      )}
    </span>
  )
}
