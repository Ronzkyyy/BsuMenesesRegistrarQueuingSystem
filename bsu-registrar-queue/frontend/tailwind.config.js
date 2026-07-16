/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bsu: {
          primary: '#be185d',
          'primary-light': '#ec4899',
          'primary-dark': '#831843',
          gold: '#f59e0b',
          'gold-light': '#fbbf24',
          'gold-dark': '#d97706',
        },
      },
    },
  },
  plugins: [],
}