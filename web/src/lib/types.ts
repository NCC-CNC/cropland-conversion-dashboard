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
}

export type ClassArrays = Record<string, number[]>;

export interface IntervalCells {
  natural_ha: ClassArrays;
  converted_ha: ClassArrays;
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
}

export interface Summary {
  cellCount: number;
  intervals: IntervalSummary[];
}
