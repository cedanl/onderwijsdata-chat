import { useOnline } from '../hooks/useOnline'
import { connectionStatus, connectionStatusText } from '../connectionStatus'

// The connection status in a composer footer (#532, WCAG 4.1.3). The live region is always mounted,
// empty while the connection is fine: a region mounted together with its text is often not announced.
export default function ConnectionStatus({ connected }) {
  const status = connectionStatus({ online: useOnline(), connected })
  return (
    <span className="ws-reconnecting" role="status" aria-live="polite">
      {status !== 'ok' && (
        <>
          <span className="ws-dot" aria-hidden="true" />
          {connectionStatusText(status)}
        </>
      )}
    </span>
  )
}
