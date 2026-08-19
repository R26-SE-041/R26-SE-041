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
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        // Brand — indigo
        brand: {
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          950: '#1e1b4b',
        },
        // Accent — violet/purple
        accent: {
          300: '#d8b4fe',
          400: '#c084fc',
          500: '#a855f7',
          600: '#9333ea',
        },
        // App background surfaces
        surface: {
          950: '#080811',
          900: '#0c0c18',
          800: '#10101f',
          700: '#16162a',
          600: '#1e1e38',
        },
        // UI greys — separate name to avoid Tailwind built-in conflict
        ui: {
          50:  'rgba(255,255,255,0.95)',
          100: 'rgba(255,255,255,0.85)',
          200: 'rgba(255,255,255,0.70)',
          300: 'rgba(255,255,255,0.55)',
          400: 'rgba(255,255,255,0.40)',
          500: 'rgba(255,255,255,0.28)',
          600: 'rgba(255,255,255,0.16)',
          700: 'rgba(255,255,255,0.08)',
          800: 'rgba(255,255,255,0.04)',
        },
      },
      backgroundImage: {
        // Page background — subtle radial blooms
        'page-gradient': [
          'radial-gradient(ellipse 80% 50% at 50% -5%, rgba(99,102,241,0.13) 0%, transparent 60%)',
          'radial-gradient(ellipse 55% 40% at 85% 90%, rgba(168,85,247,0.07) 0%, transparent 55%)',
          'linear-gradient(180deg, #080811 0%, #0c0c18 100%)',
        ].join(', '),
        'hero-gradient': [
          'radial-gradient(ellipse 80% 50% at 50% -5%, rgba(99,102,241,0.13) 0%, transparent 60%)',
          'radial-gradient(ellipse 55% 40% at 85% 90%, rgba(168,85,247,0.07) 0%, transparent 55%)',
          'linear-gradient(180deg, #080811 0%, #0c0c18 100%)',
        ].join(', '),
        'brand-gradient':  'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
        'danger-gradient': 'linear-gradient(135deg, #ef4444 0%, #e11d48 100%)',
      },
      animation: {
        'pulse-slow': 'pulse 3.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bar-wave':   'bar-wave 1.5s ease-in-out infinite',
        'fade-up':    'fade-up 0.4s ease-out both',
        'ping-slow':  'ping 2s cubic-bezier(0,0,0.2,1) infinite',
      },
      keyframes: {
        'bar-wave': {
          '0%, 100%': { transform: 'scaleY(0.3)' },
          '50%':       { transform: 'scaleY(1.0)' },
        },
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
      },
      boxShadow: {
        'card': '0 4px 32px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.06)',
      },
      borderRadius: {
        '4xl': '2rem',
      },
    },
  },
  plugins: [],
}

export default config
