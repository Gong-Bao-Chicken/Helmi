import { svelte } from "@sveltejs/vite-plugin-svelte";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // Relative base so the build works from any static host path (e.g. GitHub Pages).
  base: "./",
  plugins: [svelte(), tailwindcss()],
  test: {
    include: ["src/**/*.test.ts"],
  },
});
