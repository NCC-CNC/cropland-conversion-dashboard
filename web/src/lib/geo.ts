import type { PolygonGeometry } from './types';

const R = 6371008.8; // mean Earth radius in metres

/** Approximate geodesic area of a polygon's outer ring, in square kilometres. */
export function polygonAreaKm2(poly: PolygonGeometry): number {
  const ring = poly.coordinates[0] ?? [];
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[i + 1];
    sum += ((x2 - x1) * Math.PI) / 180 * (2 + Math.sin((y1 * Math.PI) / 180) + Math.sin((y2 * Math.PI) / 180));
  }
  return Math.abs((sum * R * R) / 2) / 1e6;
}
