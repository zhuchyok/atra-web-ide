/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,svelte}"
  ],
  theme: {
    extend: {
      colors: {
        'atra-primary': '#667eea',
        'atra-secondary': '#764ba2',
        'atra-dark': '#1a1a2e',
        'atra-darker': '#16213e',
        'atra-accent': '#0f3460',
      }
    }
  },
  plugins: []
}
