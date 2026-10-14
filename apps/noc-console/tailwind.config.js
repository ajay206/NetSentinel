/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: '#0f172a',
        'surface-2': '#1e293b',
        'surface-3': '#334159',
        slate: {
          900: '#0f172a',
          800: '#1e293b',
          700: '#334159',
          600: '#475569',
          500: '#64748b',
          400: '#94a3b8',
        },
      },
    },
  },
  plugins: [],
};
