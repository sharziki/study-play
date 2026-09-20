import type { Config } from "tailwindcss";

/* The borrowed components lean on semantic colour names (bg-secondary,
 * text-primary-foreground, ring-ring). Without these mappings those classes
 * resolve to nothing, which is silent: the progress track turns invisible and
 * the white star on a path node renders as a dark outline. Found by
 * screenshot, not by the build, because unknown utilities are not an error. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
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
