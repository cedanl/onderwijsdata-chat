import ModelPicker from './ModelPicker'

export default function ChatInputFooter({
  connected,
  busy,
  models,
  selectedModel,
  onModelChange,
  onStop,
  onSend,
  canSend,
}) {
  return (
    <div className="chat-input-footer">
      {!connected && (
        <span className="ws-reconnecting">
          <span className="ws-dot" />
          Verbinding herstellen...
        </span>
      )}
      {busy ? (
        <button type="button" className="send-btn" onClick={onStop} title="Stop genereren">
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