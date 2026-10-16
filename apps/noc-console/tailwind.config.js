/** @type {import('tailwindcss').Config} */
// Modern bento theme (matching mockup c.png / c.html):
// soft off-white background (#F4F1EA), tile background (#FFFFFF), navy (#09254A), cyan (#6DCFF6)
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Nunito', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Urbanist', 'Nunito', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        'bento': '20px',
      },
      colors: {
        navy: {
          DEFAULT: '#09254A',
          mid: '#0E3A6B',
          light: '#12507A',
        },
        cyan: {
          DEFAULT: '#6DCFF6',
          dark: '#3BA8D4',
        },
        bento: {
          bg: '#F4F1EA',
          tile: '#FFFFFF',
          border: '#EEE8DC',
          muted: '#6B7280',
        },
        // Rebuild slate scale for compatibility with existing utility classes
        slate: {
          50: '#FFFFFF',
          100: '#F4F1EA',
          200: '#E5E0D8',
          300: '#D4CFC5',
          400: '#9CA3AF',
          500: '#6B7280',
          600: '#4B5563',
          700: '#374151',
          800: '#1F2937',
          900: '#09254A',
          950: '#040F20',
        },
        // Rebuild sky scale
        sky: {
          100: '#E0F2FE',
          200: '#BAE6FD',
          300: '#7DD3FC',
          400: '#6DCFF6',
          500: '#3BA8D4',
          600: '#0284C7',
          700: '#0369A1',
          800: '#075985',
          900: '#0C4A6E',
        },
      },
    },
  },
  plugins: [],
};
