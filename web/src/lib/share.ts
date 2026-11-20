import type { PolygonGeometry } from './types';

export interface SharedState {
  area?: string;
  poly?: PolygonGeometry;
}

const DECIMALS = 4; // about 10 m, plenty for a 1 km grid

/** Encode the selected area and shape into a URL hash such as `#a=id&s=lon,lat;lon,lat`. */
export function encodeShare(areaId: string, poly: PolygonGeometry | null): string {
  const parts = [`a=${encodeURIComponent(areaId)}`];
  const ring = poly?.coordinates[0];
  if (ring && ring.length >= 4) {
    const pts = ring.slice(0, -1).map(([x, y]) => `${x.toFixed(DECIMALS)},${y.toFixed(DECIMALS)}`);
    parts.push(`s=${pts.join(';')}`);
  }
  return `#${parts.join('&')}`;
}

/** Parse a hash made by encodeShare. Returns an empty object for anything invalid. */
export function decodeShare(hash: string): SharedState {
  const out: SharedState = {};
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  const area = params.get('a');
  if (area) out.area = area;
  const s = params.get('s');
  if (s) {
    const pts: number[][] = [];
    for (const pair of s.split(';')) {
      const [x, y] = pair.split(',').map(Number);
      if (!Number.isFinite(x) || !Number.isFinite(y) || Math.abs(x) > 180 || Math.abs(y) > 90) return out;
      pts.push([x, y]);
    }
    if (pts.length >= 3) out.poly = { type: 'Polygon', coordinates: [[...pts, pts[0]]] };
  }
  return out;
}
