import ModelPicker from './ModelPicker'
import MessageCounter from './MessageCounter'
import ConnectionStatus from './ConnectionStatus'
import { messageLengthState } from '../messageLength'

export default function ChatInputFooter({
  connected,
  opgegeven,
  bijwerken,
  onVerbindOpnieuw,
  busy,
  stopping = false,
  models,
  selectedModel,
  onModelChange,
  onStop,
  onSend,
  canSend,
  text = '',
  max,
}) {
  const length = messageLengthState(text, max)
  return (
    <div className="chat-input-footer">
      <ConnectionStatus connected={connected} opgegeven={opgegeven} bijwerken={bijwerken} onOpnieuw={onVerbindOpnieuw} />
      <MessageCounter {...length} />
      {busy ? (
        // Pressed once is enough: the server needs a moment to end a tool it cannot interrupt (#1087).
        <button
          type="button" className="send-btn" onClick={onStop} aria-disabled={stopping}
          title={stopping ? 'Stoppen…' : 'Stop genereren'} aria-label={stopping ? 'Stoppen…' : 'Stop genereren'}
        >
          <svg viewBox="0 0 24 24" fill="currentColor" style={{ width: 14, height: 14 }}><rect x="5" y="5" width="14" height="14" rx="2" /></svg>
        </button>
      ) : (
        <button type="button" className="send-btn" onClick={onSend} aria-label="Verstuur bericht" aria-disabled={!canSend}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
        </button>
      )}
      {models.length > 0 && (
        <ModelPicker models={models} value={selectedModel} onChange={onModelChange} />
      )}
    </div>
  )
}