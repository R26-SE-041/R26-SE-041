import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      borderRadius: { lg: "8px", xl: "12px", "2xl": "18px", "3xl": "24px" },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        serif: ["var(--font-display)", "Georgia", "serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      colors: {
        emerald: { 400: "#91a184", 500: "#6e8362", 600: "#52654b", 700: "#42543a" },
        green: { 400: "#91a184", 500: "#6e8362", 600: "#52654b", 700: "#42543a" },
        red: { 400: "#c77f6d", 500: "#b66350", 600: "#a04436", 700: "#85382d" },
        amber: { 400: "#b49a65", 500: "#a18850", 600: "#906e30", 700: "#725720" },
        orange: {
          50: "#faf4ef", 100: "#f2e5dc", 200: "#e8cbbc",
          300: "#dfb39d", 400: "#dc9678", 500: "#d97757",
          600: "#c56648", 700: "#a95037", 800: "#82442f", 900: "#674432",
        },
        // Deep navy base
        navy: {
          950: "#03050f",
          900: "#060a1a",
          800: "#0d1433",
          700: "#142050",
        },
        // Legacy utility names now map to the warm editorial palette.
        violet: {
          400: "#e89576",
          500: "#d8653b",
          600: "#c65431",
        },
        // Cyan accent
        cyan: {
          400: "#b69a78",
          500: "#8d6f50",
        },
        // Glass surfaces
        glass: {
          white: "rgba(255, 255, 255, 0.06)",
          border: "rgba(255, 255, 255, 0.1)",
          hover: "rgba(255, 255, 255, 0.10)",
        },
      },
      backgroundImage: {
        "hero-gradient":
          "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(124,58,237,0.35) 0%, rgba(6,11,26,0) 70%), radial-gradient(ellipse 60% 40% at 80% 80%, rgba(34,211,238,0.15) 0%, transparent 70%)",
        "card-gradient":
          "linear-gradient(135deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.02) 100%)",
        "progress-gradient": "linear-gradient(var(--accent), var(--accent))",
        "button-gradient": "linear-gradient(var(--primary), var(--primary))",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.5s ease-out",
        "slide-up": "slideUp 0.4s ease-out",
        "spin-slow": "spin 8s linear infinite",
        shimmer: "shimmer 2s linear infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-1000px 0" },
          "100%": { backgroundPosition: "1000px 0" },
        },
      },
      backdropBlur: {
        xs: "2px",
      },
      boxShadow: {
        glass: "0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.1)",
        "glass-hover": "0 16px 48px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.15)",
        glow: "0 0 40px rgba(139,92,246,0.3)",
        "glow-cyan": "0 0 30px rgba(34,211,238,0.2)",
        "card": "0 4px 24px rgba(0,0,0,0.3)",
      },
    },
  },
  plugins: [],
};

export default config;
