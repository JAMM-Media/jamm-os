// frontend/tailwind.config.ts
import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-inter)', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
      },
      colors: {
        brand: {
          DEFAULT: '#1F3148',
          light: '#4A7FA5',
          muted: '#7DA3C4',
          dark: '#1A2535',
          btn: '#3A6A94',
        },
        surface: {
          page: '#E4E6EA',
          card: '#EDEEF0',
          border: '#C8CDD6',
          input: '#F7F7F8',
        },
        dark: {
          page: '#2D2D2D',
          card: '#383838',
          border: '#484848',
          sidebar: '#1A2535',
        },
        status: {
          green: '#D1FAE5',
          'green-text': '#065F46',
          blue: '#DBEAFE',
          'blue-text': '#1E40AF',
          amber: '#FEF3C7',
          'amber-text': '#92400E',
          red: '#FEE2E2',
          'red-text': '#991B1B',
        },
      },
      borderRadius: {
        badge: '9999px',
        card: '8px',
        modal: '10px',
      },
    },
  },
  plugins: [],
}

export default config
