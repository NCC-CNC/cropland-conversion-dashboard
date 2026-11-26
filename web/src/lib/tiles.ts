import { bboxIntersects } from './summary';
import type { AreaIndex, BBox, Cells, ClassArrays, IntervalCells, RegionEntry, TileEntry } from './types';

/** Tiles whose cell extent intersects the box (a drawn shape's bounding box, for example). */
export function tilesForBBox(index: AreaIndex, box: BBox): TileEntry[] {
  return index.tiles.filter((t) => bboxIntersects(t.bbox, box));
}

/** Tiles to fetch to cover a region, in index order. Unknown region gives none. */
export function tilesForRegion(index: AreaIndex, regionId: string): TileEntry[] {
  const reg = index.region_summary.find((r) => r.id === regionId);
  if (!reg) return [];
  const want = new Set(reg.tiles);
  return index.tiles.filter((t) => want.has(t.id));
}

/** Union of the extents of some tiles, or null for none. */
export function unionBBox(tiles: TileEntry[]): BBox | null {
  if (tiles.length === 0) return null;
  const out: BBox = [Infinity, Infinity, -Infinity, -Infinity];
  for (const t of tiles) {
    out[0] = Math.min(out[0], t.bbox[0]);
    out[1] = Math.min(out[1], t.bbox[1]);
    out[2] = Math.max(out[2], t.bbox[2]);
    out[3] = Math.max(out[3], t.bbox[3]);
  }
  return out;
}

/** Regions with cells in this area, sorted by name then id, for the picker. */
export function regionOptions(index: AreaIndex): RegionEntry[] {
  return index.region_summary
    .filter((r) => r.cells > 0)
    .sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
}

/** Province code from a region id such as `aspen-parkland-sk`, or null. */
export function regionProvince(id: string): 'MB' | 'SK' | null {
  if (id.endsWith('-mb')) return 'MB';
  if (id.endsWith('-sk')) return 'SK';
  return null;
}

/** Picker label: the name with the province code, since an ecoregion can span the border. */
export function regionLabel(r: Pick<RegionEntry, 'id' | 'name'>): string {
  const p = regionProvince(r.id);
  return p ? `${r.name} (${p})` : r.name;
}

function pad(a: number[] | undefined, n: number): number[] {
  return a ?? new Array<number>(n).fill(0);
}

function mergeClassArrays(parts: (ClassArrays | undefined)[], lens: number[], classes: string[]): ClassArrays {
  const out: ClassArrays = {};
  for (const c of classes) out[c] = parts.flatMap((p, i) => pad(p?.[c], lens[i]));
  return out;
}

/**
 * Concatenate normalised tiles into one Cells. A class or target missing from a tile means zero there
 * (the pipeline leaves all-zero arrays out), so it is zero-filled. Summing the merged tiles gives the
 * same totals as summing each tile on its own.
 */
export function mergeCells(parts: Cells[]): Cells {
  const lens = parts.map((p) => p.lon.length);
  const keys = new Set<string>();
  for (const p of parts) for (const k of Object.keys(p.intervals)) keys.add(k);
  const intervals: Record<string, IntervalCells> = {};
  for (const key of keys) {
    const ivs = parts.map((p) => p.intervals[key]);
    const classes = new Set<string>();
    const targets = new Set<string>();
    for (const iv of ivs) {
      if (!iv) continue;
      for (const c of Object.keys(iv.natural_ha)) classes.add(c);
      for (const [t, m] of Object.entries(iv.converted_ha)) {
        targets.add(t);
        for (const c of Object.keys(m)) classes.add(c);
      }
    }
    const cls = [...classes];
    const converted: Record<string, ClassArrays> = {};
    for (const t of targets) {
      converted[t] = mergeClassArrays(
        ivs.map((iv) => iv?.converted_ha[t]),
        lens,
        cls,
      );
    }
    intervals[key] = { natural_ha: mergeClassArrays(ivs.map((iv) => iv?.natural_ha), lens, cls), converted_ha: converted };
  }
  const hasRegion = parts.some((p) => p.region);
  return {
    lon: parts.flatMap((p) => p.lon),
    lat: parts.flatMap((p) => p.lat),
    area_ha: parts.flatMap((p) => p.area_ha),
    intervals,
    ...(hasRegion ? { region: parts.flatMap((p, i) => p.region ?? new Array<number>(lens[i]).fill(-1)) } : {}),
  };
}

/** Keep only the listed cell indices, in order. */
export function subsetCells(cells: Cells, idx: number[]): Cells {
  const pick = (a: number[]) => idx.map((i) => a[i]);
  const pickMap = (m: ClassArrays): ClassArrays => Object.fromEntries(Object.entries(m).map(([k, a]) => [k, pick(a)]));
  const intervals: Record<string, IntervalCells> = {};
  for (const [k, iv] of Object.entries(cells.intervals)) {
    intervals[k] = {
      natural_ha: pickMap(iv.natural_ha),
      converted_ha: Object.fromEntries(Object.entries(iv.converted_ha).map(([t, m]) => [t, pickMap(m)])),
    };
  }
  return {
    lon: pick(cells.lon),
    lat: pick(cells.lat),
    area_ha: pick(cells.area_ha),
    intervals,
    ...(cells.region ? { region: pick(cells.region) } : {}),
  };
}

/** Cells of one region from merged tiles (matches the `region` column against `index.regions`). */
export function cellsOfRegion(cells: Cells, index: Pick<AreaIndex, 'regions'>, regionId: string): Cells {
  const want = index.regions.indexOf(regionId);
  if (want < 0 || !cells.region) return subsetCells(cells, []);
  const idx: number[] = [];
  for (let i = 0; i < cells.region.length; i++) if (cells.region[i] === want) idx.push(i);
  return subsetCells(cells, idx);
}
