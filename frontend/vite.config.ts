import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: { rollupOptions: { output: { manualChunks: { math: ['katex'] } } } },
  server: {
    host: '127.0.0.1',
    strictPort: true,
    proxy: { '/v1': loadEnv(mode, '.', 'ZONE_BACKEND_URL').ZONE_BACKEND_URL || 'http://127.0.0.1:8765' },
  },
  test: { include: ['src/**/*.test.{ts,tsx}'], environment: 'jsdom', setupFiles: './src/test-setup.ts', testTimeout: 20_000 },
}))
