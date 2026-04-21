import path from 'path'
import fs from 'fs'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const root = process.cwd()
const resolve = (...dir) => {
  return path.resolve(root, ...dir)
}
const config = JSON.parse(fs.readFileSync(resolve('..', 'config.json'), 'utf-8'))

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    port: config.frontend.port,
    proxy: {
      '/api': `http://localhost:${config.server.port}`,
    },
  },
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve('src'),
    },
  },
})
