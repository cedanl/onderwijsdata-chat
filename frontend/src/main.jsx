import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import '@fontsource-variable/inter'
import './styles.css'
import { registreerServiceWorker } from './registreerServiceWorker'
import { startInstallatieAanbod } from './installeerApp'
import { bewaarVraagUitUrl, luisterNaarVraagInUrl } from './voorgevuldeVraag'

// Before the router reads the address: a question in the link (#709) waits in sessionStorage, out of the URL. Also
// later, when a link only changes the fragment of the open app (#806).
bewaarVraagUitUrl()
luisterNaarVraagInUrl()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

startInstallatieAanbod()
registreerServiceWorker()
