/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // OKLCH values resolved to hex for Tailwind compat. Source of truth
        // is design tokens — keep the OKLCH values in CSS variables.
        paper: "var(--color-paper)",
        surface: "var(--color-surface)",
        ink: "var(--color-ink)",
        subtext: "var(--color-subtext)",
        signal: "var(--color-signal)",
        verified: "var(--color-verified)",
        rejected: "var(--color-rejected)",
        rule: "var(--color-rule)",
      },
      fontFamily: {
        display: ['"Space Grotesk"', "system-ui", "sans-serif"],
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        // Modular scale, ratio ≈ 1.25
        "display-xl": ["clamp(3rem, 6vw + 1rem, 5.5rem)", { lineHeight: "1.02", letterSpacing: "-0.025em" }],
        "display-lg": ["clamp(2.25rem, 4vw + 0.5rem, 3.5rem)", { lineHeight: "1.05", letterSpacing: "-0.02em" }],
        "display-md": ["1.875rem", { lineHeight: "1.1", letterSpacing: "-0.015em" }],
        "title": ["1.25rem", { lineHeight: "1.25", letterSpacing: "-0.005em" }],
        "body": ["1rem", { lineHeight: "1.55" }],
        "small": ["0.875rem", { lineHeight: "1.5" }],
        "label": ["0.75rem", { lineHeight: "1.4", letterSpacing: "0.06em" }],
      },
      borderRadius: {
        DEFAULT: "2px",
        sm: "1px",
        md: "4px",
      },
      boxShadow: {
        card: "0 1px 0 0 var(--color-rule)",
        lift: "0 8px 24px -16px rgba(40, 40, 50, 0.18)",
      },
      transitionTimingFunction: {
        "out-quart": "cubic-bezier(0.25, 1, 0.5, 1)",
        "out-quint": "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        rise: "rise 0.42s cubic-bezier(0.25, 1, 0.5, 1) both",
      },
    },
  },
  plugins: [],
};
