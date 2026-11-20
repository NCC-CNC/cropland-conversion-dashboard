// MapLibre GL JS v6 loads its worker (and a shared chunk it imports) from files
// next to the main bundle. Vite flattens the main bundle into assets/, so the
// worker files must be served from a fixed path instead. This copies them to
// public/maplibre/ (git-ignored) before dev and build; src/main.ts calls
// setWorkerUrl with that path.
import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = join(webRoot, 'node_modules', 'maplibre-gl', 'dist');
const dest = join(webRoot, 'public', 'maplibre');
mkdirSync(dest, { recursive: true });
for (const f of ['maplibre-gl-worker.mjs', 'maplibre-gl-shared.mjs']) {
  copyFileSync(join(src, f), join(dest, f));
}
