import { useId, useState } from 'react'
import { conversationMarkdown, conversationNotebook, exportBestandsnaam } from '../conversationExport'
import { useDialog } from '../hooks/useDialog'
import { saveFile } from '../saveFile'

const DATUM = new Intl.DateTimeFormat('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })

function ExportDialog({ messages, save, onClose }) {
  const dialogRef = useDialog(onClose)
  const titleId = useId()
  const formaatNaam = useId()
  const [snippets, setSnippets] = useState(true)
  const [fouten, setFouten] = useState(false)
  const [formaat, setFormaat] = useState('markdown')
  const notebook = formaat === 'notebook'

  function download() {
    const datum = DATUM.format(new Date())
    if (notebook) {
      // Een notebook is de code: de codecellen gaan altijd mee (#1247).
      const json = JSON.stringify(conversationNotebook(messages, { fouten, datum }), null, 1) + '\n'
      save(new Blob([json], { type: 'application/x-ipynb+json' }), exportBestandsnaam(messages, '.ipynb'))
    } else {
      const markdown = conversationMarkdown(messages, { snippets, fouten, datum })
      save(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }), exportBestandsnaam(messages, '.md'))
    }
    onClose()
  }

  return (
    <div className="confirm-overlay">
      <div className="confirm-dialog" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
        <p className="confirm-message" id={titleId}>Exporteer dit gesprek als bestand</p>
        <fieldset className="export-formaat">
          <legend className="export-formaat-legend">Formaat</legend>
          <label className="export-option">
            <input type="radio" name={formaatNaam} value="markdown" checked={!notebook} onChange={() => setFormaat('markdown')} />
            Markdown
          </label>
          <label className="export-option">
            <input type="radio" name={formaatNaam} value="notebook" checked={notebook} onChange={() => setFormaat('notebook')} />
            Jupyter-notebook (.ipynb)
          </label>
        </fieldset>
        <label className="export-option">
          <input type="checkbox" checked={snippets || notebook} disabled={notebook} onChange={e => setSnippets(e.target.checked)} />
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

// The conversation as an audit file, with the code that reproduces each step (#366): Markdown, or a Jupyter notebook (#1247).
// onClose: de dialoog is dicht (geannuleerd of gedownload); het ⋯-menu in de navbar sluit dan ook (#596).
export default function ConversationExport({ messages, save = saveFile, onClose }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" className="export-conversation-btn" onClick={() => setOpen(true)}>
        Exporteer gesprek
      </button>
      {open && <ExportDialog messages={messages} save={save} onClose={() => { setOpen(false); onClose?.() }} />}
    </>
  )
}
