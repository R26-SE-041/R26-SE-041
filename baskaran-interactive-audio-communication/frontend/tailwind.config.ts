import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Google Sans"', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        // Primary blue accent (NotebookLM-style)
        blue: {
          50:  '#EEF3FD',
          100: '#D9E6FB',
          200: '#B3CCF7',
          300: '#7AAAF1',
          400: '#4A84E8',
          500: '#1A73E8',
          600: '#1557B0',
          700: '#0F3D80',
        },
        // Warm neutral palette — paper, cream, parchment
        sand: {
          50:  '#FAFAF8',
          100: '#F5F4EF',
          200: '#EAE8E0',
          300: '#DBD8CC',
          400: '#C8C4B4',
          500: '#A8A390',
          600: '#7A7460',
          700: '#5A5548',
        },
        // Text shades
        ink: {
          DEFAULT: '#1C1C1E',
          soft:    '#3C3C40',
          muted:   '#6E6E73',
          faint:   '#AEAEB2',
          ghost:   '#D1D1D6',
        },
        // Surfaces
        surface: {
          DEFAULT: '#FFFFFF',
          50:  '#FFFFFF',
          100: '#F5F4EF',
          200: '#EAE8E0',
          300: '#E0DDD4',
          sidebar: '#F0EEE8',
        },
        // Semantic
        success: '#34A853',
        warning: '#FBBC04',
        danger:  '#EA4335',
      },
      backgroundImage: {
        'page-bg': 'linear-gradient(160deg, #F5F4EF 0%, #EDE9E0 100%)',
        'sidebar-bg': 'linear-gradient(180deg, #F0EEE8 0%, #E8E5DC 100%)',
        'blue-gradient': 'linear-gradient(135deg, #1A73E8 0%, #4A84E8 100%)',
        'blue-soft': 'linear-gradient(135deg, #EEF3FD 0%, #D9E6FB 100%)',
      },
      animation: {
        'pulse-slow':  'pulse 3.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bar-wave':    'bar-wave 1.5s ease-in-out infinite',
        'fade-up':     'fade-up 0.35s ease-out both',
        'fade-in':     'fade-in 0.25s ease-out both',
        'scale-in':    'scale-in 0.2s ease-out both',
        'ping-slow':   'ping 2.5s cubic-bezier(0,0,0.2,1) infinite',
        'spin-slow':   'spin 2s linear infinite',
        'record-ring': 'record-ring 1.5s ease-in-out infinite',
      },
      keyframes: {
        'bar-wave': {
          '0%, 100%': { transform: 'scaleY(0.3)' },
          '50%':      { transform: 'scaleY(1.0)' },
        },
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to:   { opacity: '1' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.94)' },
          to:   { opacity: '1', transform: 'scale(1)' },
        },
        'record-ring': {
          '0%':   { transform: 'scale(1)', opacity: '0.7' },
          '50%':  { transform: 'scale(1.18)', opacity: '0.3' },
          '100%': { transform: 'scale(1)', opacity: '0.7' },
        },
      },
      boxShadow: {
        'card':    '0 1px 3px rgba(0,0,0,0.08), 0 4px 16px rgba(0,0,0,0.06)',
        'card-md': '0 2px 8px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.07)',
        'card-lg': '0 4px 16px rgba(0,0,0,0.08), 0 16px 40px rgba(0,0,0,0.06)',
        'blue':    '0 2px 12px rgba(26,115,232,0.28)',
        'inner':   'inset 0 1px 3px rgba(0,0,0,0.07)',
      },
      borderRadius: {
        '4xl': '2rem',
      },
    },
  },
  plugins: [],
}

export default config
