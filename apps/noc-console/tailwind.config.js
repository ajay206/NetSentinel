/** @type {import('tailwindcss').Config} */
// Deck theme (light): palette and fonts from the Phase 1 study deck
// (NetSentinel_Phase1_Study.pptx). See docs/handbook/03-services.md.
const deck = {
  navy: '#09254A', // headings, body, header bar
  navyMid: '#2A4A73',
  cyan: '#6DCFF6', // sky accent
  cyanDark: '#1677A0', // AA accent / active nav on white
  cyanLight: '#A3E5F9',
  cyanMist: '#E8F5FA',
  mauve: '#7A748A',
  mauveDark: '#5A5566', // muted text, WCAG AA on white (~7:1)
  copper: '#C89B7B',
  grey: '#A8A8A8',
  mist: '#D9DEE5', // card borders
  page: '#F4F7FB',
  white: '#FFFFFF',
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
        surface: deck.white,
        'surface-2': deck.page,
        'surface-3': deck.mist,
        // Neutral scale: existing slate-* classes now read as a light theme.
        // High numbers = surfaces (page/cards); low numbers = navy text.
        slate: {
          50: deck.white,
          100: deck.navy,
          200: deck.navy,
          300: '#1E3A5F',
          400: deck.mauveDark,
          500: deck.mauveDark,
          600: '#C5CCD6',
          700: deck.mist,
          800: '#EEF2F6',
          900: deck.white,
          950: deck.page,
        },
        // Accent: 300–400 are dark enough for text on white; 500–600 for fills.
        sky: {
          100: deck.cyanMist,
          200: '#0E4A6C',
          300: deck.cyanDark,
          400: deck.cyanDark,
          500: '#2196C9',
          600: deck.cyanDark,
          700: '#0A5478',
          800: '#114C75',
          900: deck.navy,
        },
      },
      boxShadow: {
        card: '0 1px 2px rgba(9, 37, 74, 0.06), 0 6px 16px rgba(9, 37, 74, 0.06)',
      },
    },
  },
  plugins: [],
};
