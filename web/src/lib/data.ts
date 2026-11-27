import { mergeCells } from './tiles';
import type {
  AreaEntry,
  AreaIndex,
  Cells,
  ClassArrays,
  Meta,
  ProvinceSummary,
  RawCells,
  RawTile,
  TileEntry,
} from './types';

const base = import.meta.env.BASE_URL;

/** Read a response as JSON, or throw an error that names the file and says what went wrong. */
export async function readJson<T>(res: Response, path: string): Promise<T> {
  if (!res.ok) {
    throw new Error(`Could not load ${path}: the server answered HTTP ${res.status}${res.status === 404 ? ' (file not found)' : ''}.`);
  }
  const text = await res.text();
  try {
    return JSON.parse(text) as T;
  } catch {
    const looksHtml = /^\s*<(!doctype|html)/i.test(text);
    throw new Error(
      looksHtml
        ? `Could not load ${path}: the server sent a web page instead of data, so the file is probably missing or the dev server needs a restart.`
        : `Could not load ${path}: the file is not valid JSON.`,
    );
  }
}

async function getJson<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${base}data/${path}`);
  } catch {
    throw new Error(`Could not load ${path}: the request failed (network error or offline).`);
  }
  return readJson<T>(res, path);
}

/** Flat form has arrays as values (crop only); the nested form has objects keyed by target. */
function isFlat(conv: ClassArrays | Record<string, ClassArrays>): boolean {
  return Object.values(conv).some((v) => Array.isArray(v));
}

/** Turn version 1 (flat) `converted_ha` into `{crop: ...}` so the rest of the app sees one shape. */
export function normaliseCells(raw: RawCells): Cells {
  const intervals: Cells['intervals'] = {};
  for (const [key, iv] of Object.entries(raw.intervals)) {
    const conv = iv.converted_ha;
    intervals[key] = {
      natural_ha: iv.natural_ha,
      converted_ha: isFlat(conv) ? { crop: conv as ClassArrays } : (conv as Record<string, ClassArrays>),
    };
  }
  const out: Cells = { lon: raw.lon, lat: raw.lat, area_ha: raw.area_ha, intervals };
  const region = (raw as RawTile).region;
  if (region) out.region = region;
  return out;
}

export const loadAreas = () => getJson<AreaEntry[]>('areas.json');
export const loadMeta = (id: string) => getJson<Meta>(`${id}/meta.json`);
export const loadCells = async (id: string) => normaliseCells(await getJson<RawCells>(`${id}/cells.json`));

/** Like getJson but returns null for any failure, so an optional file can be absent. */
async function getOptionalJson<T>(path: string): Promise<T | null> {
  try {
    return await getJson<T>(path);
  } catch {
    return null;
  }
}

/** index.json of a tiled area, or null if absent or not an index (for example an HTML fallback page). */
export async function loadIndex(id: string): Promise<AreaIndex | null> {
  const idx = await getOptionalJson<AreaIndex>(`${id}/index.json`);
  return idx && Array.isArray(idx.tiles) && Array.isArray(idx.region_summary) ? idx : null;
}

/** province_summary.json of a tiled MB or SK area, or null if absent. */
export async function loadProvinceSummary(id: string): Promise<ProvinceSummary | null> {
  const s = await getOptionalJson<ProvinceSummary>(`${id}/province_summary.json`);
  return s && s.kind === 'province_summary' && s.provinces ? s : null;
}

const tileCache = new Map<string, Promise<Cells>>();

/** Fetch one tile (cached by path). A failed fetch is not cached, so a retry can succeed. */
export function loadTile(areaId: string, tile: TileEntry): Promise<Cells> {
  const path = `${areaId}/${tile.file}`;
  let p = tileCache.get(path);
  if (!p) {
    p = getJson<RawTile>(path).then(normaliseCells);
    p.catch(() => tileCache.delete(path));
    tileCache.set(path, p);
  }
  return p;
}

/** Fetch tiles in parallel and merge them. Reports how many are done. Rejects naming the failed tile. */
export async function loadTiles(
  areaId: string,
  tiles: TileEntry[],
  onProgress?: (done: number, total: number) => void,
): Promise<Cells> {
  let done = 0;
  const parts = await Promise.all(
    tiles.map((t) =>
      loadTile(areaId, t).then(
        (c) => {
          onProgress?.(++done, tiles.length);
          return c;
        },
        (err: Error) => {
          throw new Error(`Tile ${t.id} failed to load. ${err.message}`);
        },
      ),
    ),
  );
  return mergeCells(parts);
}
