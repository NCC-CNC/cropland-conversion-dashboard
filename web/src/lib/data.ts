import type { AreaEntry, Cells, Meta } from './types';

const base = import.meta.env.BASE_URL;

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${base}data/${path}`);
  if (!res.ok) throw new Error(`Could not load ${path} (HTTP ${res.status})`);
  return (await res.json()) as T;
}

export const loadAreas = () => getJson<AreaEntry[]>('areas.json');
export const loadMeta = (id: string) => getJson<Meta>(`${id}/meta.json`);
export const loadCells = (id: string) => getJson<Cells>(`${id}/cells.json`);
