import { memo, useLayoutEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import KolomKop from './KolomKop'
import TabelScroll from './TabelScroll'
import CitedNumber from './CitedNumber'
import { rehypeCitaties } from '../citations'
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python'
import sql from 'react-syntax-highlighter/dist/esm/languages/prism/sql'
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json'
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash'
import { oneLight, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import ReasoningStep from './ReasoningStep'
import { markRecovered } from '../toolSteps'
import { useMediaQuery, NARROW_SCREEN } from '../hooks/useMediaQuery'
import CopyButton from './CopyButton'
import { splitsTelling } from '../telling'

SyntaxHighlighter.registerLanguage('python', python)
SyntaxHighlighter.registerLanguage('sql', sql)
SyntaxHighlighter.registerLanguage('json', json)
SyntaxHighlighter.registerLanguage('bash', bash)

// De inhoud van een bericht: markdown met codeblokken en citaties, het redeneerpaneel met de stappen, en het
// Telling-blok. Uit ChatPage.jsx gehaald (#696); de pagina zelf houdt geen weergave van één bericht.

function codeTheme() {
  return document.documentElement.classList.contains('dark') ? oneDark : oneLight
}

function CodeBlock({ className, children }) {
  const language = /language-(\w+)/.exec(className || '')?.[1]
  if (!language) return <code className={className}>{children}</code>
  const code = String(children).replace(/\n$/, '')
  return (
    <div className="code-block-wrap">
      <CopyButton text={code} className="copy-btn-code" />
      <SyntaxHighlighter
        language={language}
        style={codeTheme()}
        customStyle={{ borderRadius: 6, fontSize: '0.8125rem', margin: '8px 0' }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}

const MARKDOWN_COMPONENTS = {
  pre({ children }) { return <>{children}</> },
  code: CodeBlock,
  table: TabelScroll,
  th: KolomKop,
  span: CitedNumber,
}

// The code of one step, behind "Bekijk code" (#595): one tap away, without filling the phone screen before the
// answer. Long lines wrap instead of scrolling sideways.
function StapCode({ code }) {
  const thema = codeTheme()
  return (
    <details className="reasoning-step-code">
      <summary>Bekijk code</summary>
      <SyntaxHighlighter
        language="python"
        style={thema}
        wrapLongLines
        // The theme sets white-space: pre on the code element, which beats wrapLongLines.
        codeTagProps={{ style: { ...thema['code[class*="language-"]'], whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' } }}
        customStyle={{ margin: '4px 0 0', padding: 8, fontSize: 'var(--font-code)', background: 'var(--white)', border: '1px solid var(--gray-200)', borderRadius: 6 }}
      >
        {code}
      </SyntaxHighlighter>
    </details>
  )
}

// De hoogte van de open stappenlijst als de kop van de kaart in beeld staat (#609); 0 als de kaart boven of onder
// het beeld ligt, of als er niets te meten is (jsdom). Met de kop in beeld verankert de browser de scroll aan de kop
// en niet aan wat eronder wegvalt, dus dan compenseert ReasoningPanel zelf.
function zichtbareKaarthoogte(panel) {
  const content = panel?.querySelector('.reasoning-content')
  const scroller = panel?.closest('.chat-messages')
  if (!content || !scroller) return 0
  const kop = panel.getBoundingClientRect()
  const zicht = scroller.getBoundingClientRect()
  const inBeeld = kop.top >= zicht.top && kop.top < zicht.bottom
  return inBeeld ? content.getBoundingClientRect().height : 0
}

export function ReasoningPanel({ tools, tussentekst, isDone, heeftTekst = false }) {
  const [open, setOpen] = useState(!isDone) // Auto-open while tools are running
  // On a phone the code sits under its own step, folded (#595); in one block under the steps it filled the
  // screen before the answer. A wide screen keeps the block.
  const codePerStap = useMediaQuery(NARROW_SCREEN)
  const panelRef = useRef(null)
  // Wie de kaart zelf open- of dichtdeed, houdt die stand (#609): het inklappen hieronder is alleen voor de kaart
  // die vanzelf openging bij het wachten.
  const handmatig = useRef(false)
  // Op een telefoon klapt de kaart in zodra het antwoord begint (#609, #639): open bleef hij 380–430 px hoog en begon
  // het antwoord onder de vouw. Desktop ongewijzigd. Staat de kaart in beeld, dan zou het antwoord eronder omhoog
  // springen (layout-shift, #594): de scroller compenseert de weggevallen hoogte en schuift daarna vloeiend naar
  // de dichte kop, zodat het begin van het antwoord in beeld komt zonder sprong. Ligt de kaart boven het beeld
  // (de lezer is al bij het eind), dan houdt de scroll-verankering van de browser alles op zijn plek.
  // Bij de eerste antwoordtekst en niet pas bij `done` (#639): in een kort gesprek staat de scroll op 0 en valt er
  // niets te compenseren, en dan schoof bij `done` het hele antwoord omhoog (CLS 0,05). Bij de eerste regel is de
  // bubbel nog klein. Tekst waarna toch weer een stap start, was tussentekst (#393): dan gaat de kaart weer open.
  const compensatie = useRef(0)
  const stapLoopt = !!tools?.some(t => !t.done)
  const antwoordBegonnen = isDone || (heeftTekst && !stapLoopt)
  useLayoutEffect(() => {
    if (!codePerStap || handmatig.current) return
    if (antwoordBegonnen && open) {
      compensatie.current = zichtbareKaarthoogte(panelRef.current)
      setOpen(false)
    } else if (!antwoordBegonnen && stapLoopt && !open) {
      setOpen(true)
    }
  }, [antwoordBegonnen, stapLoopt, codePerStap, open])
  useLayoutEffect(() => {
    if (open || !compensatie.current) return
    const scroller = panelRef.current?.closest('.chat-messages')
    if (scroller) {
      scroller.scrollTop -= compensatie.current
      panelRef.current.scrollIntoView({ block: 'start', behavior: 'smooth' })
    }
    compensatie.current = 0
  }, [open])
  if (!tools?.length) return null
  const hasSnippets = tools.some(t => t.snippet)
  const toggle = () => { handmatig.current = true; setOpen(o => !o) }

  return (
    <div className="reasoning-panel" ref={panelRef}>
      <button type="button" className="reasoning-toggle" onClick={toggle} aria-expanded={open}>
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
        <span>Redenering ({tools.length} {tools.length === 1 ? 'stap' : 'stappen'})</span>
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: 'auto', transform: open ? 'rotate(180deg)' : '' }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div className="reasoning-content">
          {markRecovered(tools).map((t, i) => (
            <ReasoningStep key={`${t.name}-${i}`} tool={t}>
              {codePerStap && t.snippet && <StapCode code={t.snippet} />}
            </ReasoningStep>
          ))}
          {/* What the model wrote between tool rounds: worth a look, but no answer (#393). */}
          {tussentekst?.map((tekst, i) => (
            <p key={i} className="reasoning-tussentekst">{tekst}</p>
          ))}
          {hasSnippets && !codePerStap && (
            <div className="reasoning-snippets">
              {tools.map((t, i) => (
                t.snippet && (
                  <div key={`${t.name}-${i}`} className="reasoning-snippet-block">
                    <div className="reasoning-snippet-label">{t.label}</div>
                    <SyntaxHighlighter
                      language="python"
                      style={codeTheme()}
                      customStyle={{ margin: 0, background: 'transparent', padding: 0, fontSize: 'var(--font-code)' }}
                    >
                      {t.snippet}
                    </SyntaxHighlighter>
                  </div>
                )
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Parsing markdown is the costly part of a message; props are stable while a message is unchanged.
const Markdown = memo(function Markdown({ text, citaties }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeCitaties(citaties)]}
      components={MARKDOWN_COMPONENTS}
    >
      {text}
    </ReactMarkdown>
  )
})

// Het Telling-blok van de backend: de eerste zin, de rest uitklapbaar (#402). Onder de vaste
// bouwstenen (#416) staat het label er al naast; dan zonder eigen kop.
export function TellingDetails({ msg, kop = true }) {
  const { telling, samenvatting } = splitsTelling(msg.content)
  if (!telling) return null
  return (
    <details className="telling">
      <summary>{kop ? <><strong>Telling</strong> {samenvatting}</> : samenvatting || 'Toon de telling'}</summary>
      <Markdown text={telling} citaties={msg.citaties} />
    </details>
  )
}

export function MessageContent({ msg, blocks = null }) {
  if (isAwaitingFirstToken(msg)) return <div className="ai-typing"><span /><span /><span /></div>
  if (!msg.content && !msg.figures?.length && !msg.clarification && !msg.starterQuestions) return null
  const { antwoord, telling } = splitsTelling(msg.content)
  if (!telling) return <Markdown text={msg.content} citaties={msg.citaties} />
  return (
    <>
      <Markdown text={antwoord} citaties={msg.citaties} />
      {/* Met de vaste bouwstenen staat de Telling daar, op een vaste plek (#416). */}
      {!blocks && <TellingDetails msg={msg} />}
    </>
  )
}

// Started but nothing to show yet: render the typing dots instead of a bare avatar.
export function isAwaitingFirstToken(msg) {
  return !msg.done && !msg.content && !msg.tools?.length && !msg.figures?.length
}
