import { useState } from 'react'
import AlgemeneFeedbackModal from './AlgemeneFeedbackModal'

// A text button that opens the general feedback form (#600), placed next to the privacy link. The modal
// mounts on click, so useDialog sees this button as the opener and gives focus back to it on close.
export default function FeedbackLink({ className = 'privacy-link', children = 'Feedback' }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" className={className} onClick={() => setOpen(true)}>{children}</button>
      {open && <AlgemeneFeedbackModal onClose={() => setOpen(false)} />}
    </>
  )
}
