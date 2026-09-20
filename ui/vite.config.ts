import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Build straight into web_static so the existing Python server, systemd unit,
// service worker, and tailscale route all keep working untouched.
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  // web_static already holds the PWA shell files that are not part of the
  // bundle (sw.js, manifest, icons, fonts, vendored KaTeX). Vite only needs to
  // copy the assets it does not own, and emptyOutDir stays off so it never
  // deletes them.
  publicDir: "public",
  build: {
    outDir: path.resolve(__dirname, "../web_static"),
    emptyOutDir: false,
    rollupOptions: { output: { entryFileNames: "app.js", assetFileNames: "[name][extname]" } },
  },
  server: { proxy: { "/api": "http://127.0.0.1:4173" } },
});
