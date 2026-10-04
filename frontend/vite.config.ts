import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    strictPort: true,
    proxy: { '/v1': 'http://127.0.0.1:8765' },
  },
  test: { environment: 'jsdom', setupFiles: './src/test-setup.ts', testTimeout: 20_000 },
})
