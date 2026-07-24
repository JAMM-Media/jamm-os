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
        sans: ['var(--font-plus-jakarta-sans)', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        display: ['var(--font-lora)', 'Georgia', '"Times New Roman"', 'serif'],
      },
      colors: {
        brand: {
          DEFAULT: '#1F3148',
          light: '#4A7FA5',
          muted: '#7DA3C4',
          dark: '#1A2535',
          btn: '#3A6A94',
        },
        concierge: {
          DEFAULT: '#BF9640',
          muted: '#D4B06A',
        },
        surface: {
          page: '#E7E6E0',
          card: '#F0EFE9',
          border: '#C6C4BA',
          input: '#F7F6F2',
        },
        dark: {
          page: '#272620',
          card: '#32312A',
          border: '#47453C',
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
