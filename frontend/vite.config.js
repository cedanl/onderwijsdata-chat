import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { plotlyRapport } from './src/plotlyRapportBouw.js'

export default defineConfig({
  // Plotly zonder maplibre voor rapporten en dashboards (#660).
  plugins: [react(), plotlyRapport()],
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
