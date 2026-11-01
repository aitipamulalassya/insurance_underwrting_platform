/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: { extend: {
    fontFamily: { sans: ['DM Sans', 'sans-serif'], display: ['Manrope', 'sans-serif'] },
    colors: { ink: '#17233c', navy: '#172b4d', teal: '#0e9384', canvas: '#f6f8fc', line: '#e8edf4' },
    boxShadow: { soft: '0 8px 30px rgba(20, 38, 70, .06)' }
  }},
  plugins: []
}