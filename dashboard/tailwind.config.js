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
        // Modular scale, ratio ≈ 1.25. Three tiers:
        // Display: fluid (clamp), for hero headlines only.
        // UI: fixed rem, for headings within content areas.
        // Text: fixed rem, for body/labels.
        "display-xl": ["clamp(3rem, 5vw + 1rem, 5rem)", { lineHeight: "1.02", letterSpacing: "-0.025em", fontWeight: "300" }],
        "display-lg": ["clamp(2rem, 3vw + 0.5rem, 3rem)", { lineHeight: "1.08", letterSpacing: "-0.02em", fontWeight: "300" }],
        "display-md": ["1.75rem", { lineHeight: "1.15", letterSpacing: "-0.015em", fontWeight: "500" }],
        "title": ["1.25rem", { lineHeight: "1.3", letterSpacing: "-0.005em", fontWeight: "500" }],
        "subtitle": ["1.0625rem", { lineHeight: "1.4", letterSpacing: "0em", fontWeight: "500" }],
        "body": ["1rem", { lineHeight: "1.6" }],
        "small": ["0.875rem", { lineHeight: "1.55" }],
        "label": ["0.6875rem", { lineHeight: "1.4", letterSpacing: "0.06em", fontWeight: "500" }],
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
