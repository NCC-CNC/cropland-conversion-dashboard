import type { AreaEntry, Cells, ClassArrays, Meta, RawCells } from './types';

const base = import.meta.env.BASE_URL;

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${base}data/${path}`);
  if (!res.ok) throw new Error(`Could not load ${path} (HTTP ${res.status})`);
  return (await res.json()) as T;
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
  return { lon: raw.lon, lat: raw.lat, area_ha: raw.area_ha, intervals };
}

export const loadAreas = () => getJson<AreaEntry[]>('areas.json');
export const loadMeta = (id: string) => getJson<Meta>(`${id}/meta.json`);
export const loadCells = async (id: string) => normaliseCells(await getJson<RawCells>(`${id}/cells.json`));
