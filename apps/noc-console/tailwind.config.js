/** @type {import('tailwindcss').Config} */
// Deck theme: palette and fonts from the Phase 1 study deck
// (NetSentinel_Phase1_Study.pptx, ppt/theme + slide colours). See docs/handbook/03-services.md.
const deck = {
  navy: '#09254A', // deck primary (titles, dark fills)
  navyMid: '#2A4A73', // deck secondary navy
  cyan: '#6DCFF6', // deck accent
  cyanLight: '#A3E5F9',
  cyanMist: '#E8F5FA',
  mauve: '#7A748A', // deck body/muted text
  copper: '#C89B7B', // deck warm highlight
  grey: '#A8A8A8',
  mist: '#D9DEE5',
};

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Nunito', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Urbanist', 'Nunito', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        deck,
        surface: '#0d2c55',
        'surface-2': '#133158',
        'surface-3': deck.navyMid,
        // Neutral scale rebuilt around the deck navy, so every existing slate-* class follows the deck.
        slate: {
          50: '#FFFFFF',
          100: '#F5F5F5',
          200: '#E8EEF5',
          300: deck.mist,
          400: '#B4BCCB',
          500: '#9D9BB0', // lifted deck mauve, readable on navy
          600: '#4A6489',
          700: deck.navyMid,
          800: '#163862',
          900: '#0d2c55',
          950: '#061a35',
        },
        // Primary accent = deck cyan.
        sky: {
          100: deck.cyanMist,
          200: '#C9EFFB',
          300: deck.cyanLight,
          400: deck.cyan,
          500: '#3FB8E8',
          600: '#1A7AAB',
          700: '#16679A',
          800: '#114C75',
          900: '#0E3A63',
        },
      },
    },
  },
  plugins: [],
};
