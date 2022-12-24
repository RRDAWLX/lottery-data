import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const root = process.cwd()
const resolve = (...dir) => {
  return path.resolve(root, ...dir)
}

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    port: 8080,
    proxy: {
      '/api': 'http://localhost:5000',
    },
  },
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve('src'),
    },
  },
})
