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
  /** Contract version 3: data is in 100 km tiles listed by index.json, with no cells.json. */
  tiled?: boolean;
  tile_km?: number;
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
  /** Tiled data only: index into `AreaIndex.regions` per cell, -1 for none. */
  region?: number[];
}

/** A tile file: the cells.json shape plus a `region` column. */
export interface RawTile extends RawCells {
  region?: number[];
}

export interface TileEntry {
  id: string;
  file: string;
  /** WGS84 extent of the tile's cells. */
  bbox: BBox;
  cells: number;
  bytes: number;
  regions: Record<string, number>;
}

export interface RegionEntry {
  id: string;
  name: string;
  cells: number;
  area_ha: number;
  tiles: string[];
}

/** index.json of a tiled area (contract version 3). */
export interface AreaIndex {
  area_id: string;
  contract_version: number;
  tile_m: number;
  cells: number;
  /** Every ecoregion id in sorted order; a cell's `region` integer indexes this list. */
  regions: string[];
  region_summary: RegionEntry[];
  tiles: TileEntry[];
}

export interface CoverageRegion {
  id: string;
  province: string;
  run: boolean;
  region_area_km2: number;
  cell_area_km2: number;
  fraction: number;
  covered: boolean;
}

export interface Coverage {
  complete: boolean;
  regions_total: number;
  regions_run: string[];
  regions_missing?: string[];
  regions_partial?: string[];
  regions_covered: string[];
  farming_zone_area_km2: number;
  covered_area_km2: number;
  fraction: number;
  note?: string;
  regions?: CoverageRegion[];
}

export interface ProvinceTotal {
  natural_ha: number;
  converted_ha: Record<string, number>;
  converted_pct: Record<string, number | null>;
}

export interface ProvinceInterval {
  natural_ha: Record<string, number>;
  converted_ha: Record<string, Record<string, number>>;
  converted_pct: Record<string, Record<string, number | null>>;
  total: ProvinceTotal;
}

export interface ProvinceEntry {
  name: string;
  regions: string[];
  cells: number;
  area_ha: number;
  coverage: Coverage;
  intervals: Record<string, ProvinceInterval>;
}

/** province_summary.json, beside index.json for tiled MB and SK areas. */
export interface ProvinceSummary {
  kind: 'province_summary';
  area_id: string;
  generated: string;
  latest: number;
  years: { snapshots: number[]; intervals: Interval[] };
  natural_classes: string[];
  targets: string[];
  method: string;
  source: string;
  caveats: string[];
  coverage: Coverage;
  provinces: Record<string, ProvinceEntry>;
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
