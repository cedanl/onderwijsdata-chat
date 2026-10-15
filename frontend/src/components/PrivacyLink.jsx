import { useState } from 'react'
import PrivacyModal from './PrivacyModal'

// A text button that opens the privacy information as a popup (#572). The modal mounts on click, so
// useDialog sees this button as the opener and gives focus back to it on close.
export default function PrivacyLink({ className = 'privacy-link', children = 'Privacy-informatie' }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" className={className} onClick={() => setOpen(true)}>{children}</button>
      {open && <PrivacyModal onClose={() => setOpen(false)} />}
    </>
  )
}
