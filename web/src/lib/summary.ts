import booleanPointInPolygon from '@turf/boolean-point-in-polygon';
import type {
  BBox,
  Cells,
  ClassRow,
  IntervalCells,
  IntervalSummary,
  Meta,
  PolygonGeometry,
  Summary,
} from './types';
import { DEFAULT_TARGET, metaTargets } from './targets';

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

/** Sum one target's hectares over the selected cells, per natural class. */
function sumClasses(
  data: IntervalCells | undefined,
  classes: string[],
  target: string,
  indices: number[],
): { nat: number[]; conv: number[] } {
  const nat: number[] = [];
  const conv: number[] = [];
  for (const cls of classes) {
    const na = data?.natural_ha[cls];
    const ca = data?.converted_ha[target]?.[cls];
    let n = 0;
    let c = 0;
    for (const i of indices) {
      n += na?.[i] ?? 0;
      c += ca?.[i] ?? 0;
    }
    nat.push(n);
    conv.push(c);
  }
  return { nat, conv };
}

const total = (xs: number[]) => xs.reduce((a, b) => a + b, 0);

/**
 * Sum the selected cells per interval and class for the active target (default crop), then derive
 * percent and annual rate. Each interval also carries a compact total for every target in the data.
 */
export function summarize(
  cells: Cells,
  meta: Meta,
  indices: number[],
  target: string = DEFAULT_TARGET,
): Summary {
  const classes = meta.natural_classes;
  const targets = metaTargets(meta);
  const intervals: IntervalSummary[] = meta.intervals.map((iv) => {
    const key = `${iv.from}-${iv.to}`;
    const data = cells.intervals[key];
    const active = sumClasses(data, classes, target, indices);
    const rows = classes.map((cls, k) => makeRow(cls, active.nat[k], active.conv[k], iv.years));
    const targetTotals: Record<string, ClassRow> = {};
    for (const t of targets) {
      const s = t === target ? active : sumClasses(data, classes, t, indices);
      targetTotals[t] = makeRow('total', total(s.nat), total(s.conv), iv.years);
    }
    return {
      key,
      from: iv.from,
      to: iv.to,
      years: iv.years,
      rows,
      total: makeRow('total', total(active.nat), total(active.conv), iv.years),
      targetTotals,
    };
  });
  return { target, cellCount: indices.length, intervals };
}

/** One summary per target in the data, in target order. Used for the CSV and the report. */
export function summarizeTargets(cells: Cells, meta: Meta, indices: number[]): Summary[] {
  return metaTargets(meta).map((t) => summarize(cells, meta, indices, t));
}

export type SelectionStatus = 'ok' | 'few-cells' | 'outside-coverage' | 'no-natural-cells';

/** Classify a selection so the UI can show the right message. */
export function selectionStatus(cellCount: number, polyBox: BBox, areaBox: BBox): SelectionStatus {
  if (!bboxIntersects(polyBox, areaBox)) return 'outside-coverage';
  if (cellCount === 0) return 'no-natural-cells';
  if (cellCount < MIN_RELIABLE_CELLS) return 'few-cells';
  return 'ok';
}
