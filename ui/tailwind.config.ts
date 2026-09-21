import type { Config } from "tailwindcss";

/* Colour lives in tokens, not in class strings.
 *
 * Two reasons. The borrowed components lean on semantic names (bg-secondary,
 * text-primary-foreground, ring-ring), and without these mappings those
 * classes resolve to nothing — which is silent: the progress track turns
 * invisible and the white star on a path node renders as a dark outline.
 * Found by screenshot, not by the build, because an unknown utility is not an
 * error.
 *
 * And the app is dark-only by request. Tokens make that one file to change
 * instead of a `dark:` variant on every surface, each of which is a place to
 * miss one and leave a white card glowing in a dark room.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "hsl(var(--canvas))",
        surface: {
          DEFAULT: "hsl(var(--surface))",
          raised: "hsl(var(--surface-raised))",
          hover: "hsl(var(--surface-hover))",
        },
        line: {
          DEFAULT: "hsl(var(--line))",
          strong: "hsl(var(--line-strong))",
        },
        ink: {
          DEFAULT: "hsl(var(--ink))",
          muted: "hsl(var(--ink-muted))",
          faint: "hsl(var(--ink-faint))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          ink: "hsl(var(--accent-ink))",
        },
        correct: "hsl(var(--correct))",
        wrong: "hsl(var(--wrong))",

        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        secondary: "hsl(var(--secondary))",
        ring: "hsl(var(--ring))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
      },
      ringOffsetColor: { background: "hsl(var(--ring-offset-background))" },
    },
  },
} satisfies Config;
