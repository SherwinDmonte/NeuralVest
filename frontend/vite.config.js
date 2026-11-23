import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// Tailwind CSS v4 is wired in through its official Vite plugin (no tailwind.config.js needed).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true, // CORS on the backend allows exactly http://localhost:5173
  },
})
