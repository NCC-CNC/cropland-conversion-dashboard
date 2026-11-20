import { defineConfig } from 'vitest/config';

// GitHub Pages serves the site under /<repo>/. Override with VITE_BASE.
export default defineConfig({
  base: process.env.VITE_BASE ?? '/cropland-conversion-dashboard/',
  build: { chunkSizeWarningLimit: 1500 },
  test: { include: ['src/**/*.test.ts'] },
});
