import { useEffect } from 'react'

export const APP_NAME = 'openEDUdata+'

// A page name followed by the app name, the form every tab title takes (#491).
export function pageTitle(name) {
  return `${name} — ${APP_NAME}`
}

// Sets the tab title for the current page. No restore on unmount: every page sets its own
// title, so restoring would only flash the previous one.
export function useDocumentTitle(title) {
  useEffect(() => {
    if (typeof title === 'string' && title) document.title = title
  }, [title])
}
