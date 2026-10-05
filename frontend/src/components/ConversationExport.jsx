import { useId, useState } from 'react'
import { conversationMarkdown } from '../conversationExport'
import { conversationTitle } from '../conversationTitle'
import { useDialog } from '../hooks/useDialog'
import { saveFile } from '../saveFile'

const DATUM = new Intl.DateTimeFormat('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })

function ExportDialog({ messages, save, onClose }) {
  const dialogRef = useDialog(onClose)
  const titleId = useId()
  const [snippets, setSnippets] = useState(true)
  const [fouten, setFouten] = useState(false)

  function download() {
    const markdown = conversationMarkdown(messages, { snippets, fouten, datum: DATUM.format(new Date()) })
    const title = conversationTitle(messages.find(m => m.role === 'user')?.content)
    save(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }), title.replace(/[^a-zA-Z0-9]/g, '_') + '.md')
    onClose()
  }

  return (
    <div className="confirm-overlay">
      <div className="confirm-dialog" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
        <p className="confirm-message" id={titleId}>Exporteer dit gesprek als markdownbestand</p>
        <label className="export-option">
          <input type="checkbox" checked={snippets} onChange={e => setSnippets(e.target.checked)} />
          Code per stap (Python, met de bron)
        </label>
        <label className="export-option">
          <input type="checkbox" checked={fouten} onChange={e => setFouten(e.target.checked)} />
          Mislukte stappen en foutmeldingen
        </label>
        <div className="confirm-actions">
          <button type="button" className="confirm-cancel" onClick={onClose}>Annuleren</button>
          <button type="button" className="confirm-primary" onClick={download}>Download</button>
        </div>
      </div>
    </div>
  )
}

// The conversation as an audit file, with the code that reproduces each step (#366).
export default function ConversationExport({ messages, save = saveFile }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" className="export-conversation-btn" onClick={() => setOpen(true)}>
        Exporteer gesprek
      </button>
      {open && <ExportDialog messages={messages} save={save} onClose={() => setOpen(false)} />}
    </>
  )
}
