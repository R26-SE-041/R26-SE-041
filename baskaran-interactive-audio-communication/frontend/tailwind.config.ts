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
        sans: ['system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        serif: ['Georgia', 'Times New Roman', 'serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        // Warm earthy primaries
        primary: {
          DEFAULT: '#d97745',
          bright:  '#f2a06f',
          soft:    'rgba(217,119,69,0.14)',
          border:  'rgba(217,119,69,0.28)',
          // light mode overrides (referenced via CSS vars)
          light:   '#c95f32',
        },
        // Warm neutral parchment palette
        sand: {
          50:   '#fff7ea',
          100:  '#f4eadb',
          200:  '#e8dac6',
          300:  '#d9c7b2',
          400:  '#a99580',
          500:  '#927b6c',
          600:  '#705d50',
          700:  '#33261f',
          dark: '#201914',
        },
        // Surface tokens (CSS-var driven; these are fallbacks)
        surface: {
          DEFAULT: 'rgba(53,41,32,0.78)',
          soft:    'rgba(255,244,226,0.08)',
          light:   'rgba(255,255,255,0.48)',
        },
        // Semantic
        success: { DEFAULT: '#91a878', light: '#647a51' },
        warning: { DEFAULT: '#e9ad5c', light: '#c88935' },
        danger:  { DEFAULT: '#e27661', light: '#b84c3d' },
      },
      backgroundImage: {
        'page-gradient': 'linear-gradient(160deg, #201914 0%, #17120f 100%)',
        'hero-gradient': 'linear-gradient(135deg, rgba(217,119,69,0.18) 0%, rgba(175,125,73,0.10) 100%)',
        'primary-gradient': 'linear-gradient(135deg, #d97745 0%, #f2a06f 100%)',
      },
      animation: {
        'pulse-slow':   'pulse 3.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bar-wave':     'bar-wave 1.5s ease-in-out infinite',
        'fade-up':      'fade-up 0.35s ease-out both',
        'fade-in':      'fade-in 0.25s ease-out both',
        'scale-in':     'scale-in 0.2s ease-out both',
        'ping-slow':    'ping 2.5s cubic-bezier(0,0,0.2,1) infinite',
        'spin-slow':    'spin 2s linear infinite',
        'record-ring':  'record-ring 1.5s ease-in-out infinite',
        'blob-drift':   'blob-drift 9s ease-in-out infinite',
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
        'blob-drift': {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '33%':      { transform: 'translate(20px, -15px) scale(1.04)' },
          '66%':      { transform: 'translate(-15px, 10px) scale(0.97)' },
        },
      },
      boxShadow: {
        'glass':   '0 24px 70px rgba(8,4,2,0.36), inset 0 1px 0 rgba(255,255,255,0.82)',
        'glass-sm':'0 8px 32px rgba(8,4,2,0.28), inset 0 1px 0 rgba(255,255,255,0.60)',
        'primary': '0 4px 20px rgba(217,119,69,0.35)',
        'inner':   'inset 0 1px 3px rgba(0,0,0,0.10)',
      },
      borderRadius: {
        'card':   '24px',
        'btn':    '13px',
        'pill':   '50px',
        'tag':    '20px',
        '4xl':    '2rem',
      },
    },
  },
  plugins: [],
}

export default config
