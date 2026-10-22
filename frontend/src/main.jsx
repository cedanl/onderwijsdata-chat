import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import '@fontsource-variable/inter'
import './styles.css'
import { registreerServiceWorker } from './registreerServiceWorker'
import { startInstallatieAanbod } from './installeerApp'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

startInstallatieAanbod()
registreerServiceWorker()
