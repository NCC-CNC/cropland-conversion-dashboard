// Shapes follow docs/design/02_mvp_data_contract.md.

export type BBox = [number, number, number, number];

export interface AreaEntry {
  id: string;
  name: string;
  bbox: BBox;
}

export interface Interval {
  from: number;
  to: number;
  years: number;
}

export interface Meta {
  area_id: string;
  name: string;
  bbox: BBox;
  cell_size_m: number;
  snapshots: number[];
  latest: number;
  natural_classes: string[];
  intervals: Interval[];
  method: string;
  source: string;
  generated: string;
  caveats: string[];
  /** Conversion targets present in the data. Missing means crop only (contract version 1). */
  targets?: string[];
  contract_version?: number;
}

export type ClassArrays = Record<string, number[]>;

/** `converted_ha` as stored in cells.json: flat (crop only, version 1) or keyed by target (version 2). */
export interface RawIntervalCells {
  natural_ha: ClassArrays;
  converted_ha: ClassArrays | Record<string, ClassArrays>;
}

export interface RawCells {
  lon: number[];
  lat: number[];
  area_ha: number[];
  intervals: Record<string, RawIntervalCells>;
}

/** Normalised: `converted_ha` is always keyed by target. A missing target or class means zero. */
export interface IntervalCells {
  natural_ha: ClassArrays;
  converted_ha: Record<string, ClassArrays>;
}

export interface Cells {
  lon: number[];
  lat: number[];
  area_ha: number[];
  intervals: Record<string, IntervalCells>;
}

/** GeoJSON Polygon geometry, ring coordinates as [lon, lat]. */
export interface PolygonGeometry {
  type: 'Polygon';
  coordinates: number[][][];
}

export interface ClassRow {
  cls: string;
  naturalHa: number;
  convertedHa: number;
  /** Percent of baseline natural hectares that were converted, or null if no natural cover. */
  percent: number | null;
  /** Converted hectares per year over the interval. */
  ratePerYear: number;
}

export interface IntervalSummary {
  key: string;
  from: number;
  to: number;
  years: number;
  rows: ClassRow[];
  total: ClassRow;
  /** Compact total per target (every target in meta, not only the active one), for headline rows. */
  targetTotals: Record<string, ClassRow>;
}

export interface Summary {
  /** Target that `rows` and `total` describe. */
  target: string;
  cellCount: number;
  intervals: IntervalSummary[];
}
