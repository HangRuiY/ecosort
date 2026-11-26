import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发时把 /api、/docs 代理到 FastAPI（8000 端口），浏览器只访问 5173，不触发跨域。
// 直接跨域访问时（VITE_API_BASE=http://localhost:8000/api/v1），由后端 CORS 放行 localhost:5173。
const target = process.env.ECOSORT_API || 'http://localhost:8000'
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target, changeOrigin: true },
      '/agent-api': {
        target: process.env.ECOSORT_AGENT || 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/agent-api/, ''),
      },
      '/docs': { target, changeOrigin: true },
      '/openapi.json': { target, changeOrigin: true },
    },
  },
  build: { outDir: 'dist', chunkSizeWarningLimit: 1500 },
})
