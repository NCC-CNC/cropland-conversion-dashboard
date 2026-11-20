import booleanPointInPolygon from '@turf/boolean-point-in-polygon';
import type {
  BBox,
  Cells,
  ClassRow,
  IntervalSummary,
  Meta,
  PolygonGeometry,
  Summary,
} from './types';

/** Fewer cells than this in a selection means high uncertainty. */
export const MIN_RELIABLE_CELLS = 5;

export function polygonBBox(poly: PolygonGeometry): BBox {
  let w = Infinity;
  let s = Infinity;
  let e = -Infinity;
  let n = -Infinity;
  for (const ring of poly.coordinates) {
    for (const [x, y] of ring) {
      if (x < w) w = x;
      if (x > e) e = x;
      if (y < s) s = y;
      if (y > n) n = y;
    }
  }
  return [w, s, e, n];
}

export function bboxIntersects(a: BBox, b: BBox): boolean {
  return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
}

/** Indices of cells whose centroid lies inside the polygon (bbox prefilter, then point in polygon). */
export function cellsInPolygon(cells: Pick<Cells, 'lon' | 'lat'>, poly: PolygonGeometry): number[] {
  const [w, s, e, n] = polygonBBox(poly);
  const feature = { type: 'Feature' as const, properties: {}, geometry: poly };
  const out: number[] = [];
  const { lon, lat } = cells;
  for (let i = 0; i < lon.length; i++) {
    const x = lon[i];
    const y = lat[i];
    if (x < w || x > e || y < s || y > n) continue;
    if (booleanPointInPolygon([x, y], feature)) out.push(i);
  }
  return out;
}

export function makeRow(cls: string, naturalHa: number, convertedHa: number, years: number): ClassRow {
  return {
    cls,
    naturalHa,
    convertedHa,
    percent: naturalHa > 0 ? (convertedHa / naturalHa) * 100 : null,
    ratePerYear: years > 0 ? convertedHa / years : 0,
  };
}

/** Sum the selected cells per interval and class, then derive percent and annual rate. */
export function summarize(cells: Cells, meta: Meta, indices: number[]): Summary {
  const intervals: IntervalSummary[] = meta.intervals.map((iv) => {
    const key = `${iv.from}-${iv.to}`;
    const data = cells.intervals[key];
    let totalNat = 0;
    let totalConv = 0;
    const rows = meta.natural_classes.map((cls) => {
      const nat = data?.natural_ha[cls];
      const conv = data?.converted_ha[cls];
      let n = 0;
      let c = 0;
      for (const i of indices) {
        n += nat?.[i] ?? 0;
        c += conv?.[i] ?? 0;
      }
      totalNat += n;
      totalConv += c;
      return makeRow(cls, n, c, iv.years);
    });
    return {
      key,
      from: iv.from,
      to: iv.to,
      years: iv.years,
      rows,
      total: makeRow('total', totalNat, totalConv, iv.years),
    };
  });
  return { cellCount: indices.length, intervals };
}

export type SelectionStatus = 'ok' | 'few-cells' | 'outside-coverage' | 'no-natural-cells';

/** Classify a selection so the UI can show the right message. */
export function selectionStatus(cellCount: number, polyBox: BBox, areaBox: BBox): SelectionStatus {
  if (!bboxIntersects(polyBox, areaBox)) return 'outside-coverage';
  if (cellCount === 0) return 'no-natural-cells';
  if (cellCount < MIN_RELIABLE_CELLS) return 'few-cells';
  return 'ok';
}
