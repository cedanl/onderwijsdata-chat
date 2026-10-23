import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { plotlyRapport } from './src/plotlyRapportBouw.js'

export default defineConfig({
  // Plotly zonder maplibre voor rapporten en dashboards (#660).
  plugins: [react(), plotlyRapport()],
  // De manifest is de bron voor de routebudgetten (scripts/bundleBudget.js, #689); hij staat in dist/.vite, buiten
  // /assets, en wordt dus niet uitgeserveerd.
  build: { manifest: true },
  test: {
    environment: 'node',
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
