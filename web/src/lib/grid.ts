import type { Cells, Meta } from './types';

/** Upper bound on grid squares drawn, so very large areas stay responsive. */
export const MAX_GRID_CELLS = 20000;

export interface GridResult {
  data: GeoJSON.FeatureCollection<GeoJSON.Polygon>;
  drawn: number;
  total: number;
}

/** Build square polygons around cell centroids. Beyond the cap, cells are thinned evenly. */
export function buildGrid(cells: Cells, meta: Meta): GridResult {
  const total = cells.lon.length;
  const step = Math.max(1, Math.ceil(total / MAX_GRID_CELLS));
  const midLat = (meta.bbox[1] + meta.bbox[3]) / 2;
  const halfLat = meta.cell_size_m / 2 / 111320;
  const halfLon = meta.cell_size_m / 2 / (111320 * Math.cos((midLat * Math.PI) / 180));
  const first = meta.intervals[0];
  const iv = first ? cells.intervals[`${first.from}-${first.to}`] : undefined;
  const features: GeoJSON.Feature<GeoJSON.Polygon>[] = [];
  for (let i = 0; i < total; i += step) {
    const x = cells.lon[i];
    const y = cells.lat[i];
    let conv = 0;
    if (iv) for (const c of meta.natural_classes) conv += iv.converted_ha[c]?.[i] ?? 0;
    features.push({
      type: 'Feature',
      properties: { conv },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [x - halfLon, y - halfLat],
            [x + halfLon, y - halfLat],
            [x + halfLon, y + halfLat],
            [x - halfLon, y + halfLat],
            [x - halfLon, y - halfLat],
          ],
        ],
      },
    });
  }
  return { data: { type: 'FeatureCollection', features }, drawn: features.length, total };
}
