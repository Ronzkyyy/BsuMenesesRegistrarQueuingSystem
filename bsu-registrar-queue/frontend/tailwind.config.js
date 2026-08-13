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
          primary: '#E85D8E',
          'primary-light': '#F2A0BC',
          'primary-dark': '#C94577',
          peach: '#F7A76C',
          'peach-light': '#FBCBA1',
          'peach-dark': '#EF8F4E',
          gold: '#F8C95A',
          'gold-light': '#FBDB8C',
          'gold-dark': '#E0AE3E',
          surface: '#F8F9FA',
          ink: '#2D2D2D',
        },
      },
      fontFamily: {
        sans: ['Poppins', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        soft: '0 2px 12px rgba(45, 45, 45, 0.06)',
        'soft-lg': '0 8px 30px rgba(45, 45, 45, 0.10)',
      },
    },
  },
  plugins: [],
}