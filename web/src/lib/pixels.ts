// 30 m converted-pixel layer (ADR 0003): pure logic for when to show it and how to style it.

/** Selections larger than this (km2) do not show pixels. Starting value from ADR 0003, adjustable. */
export const PIXEL_MAX_KM2 = 500;
/** Zoom range the PMTiles file holds (export_tiles.py). */
export const PIXEL_MIN_ZOOM = 11;
export const PIXEL_MAX_ZOOM = 14;
export const PIXEL_SOURCE_LAYER = 'converted';

export type PixelState =
  | 'unavailable' // no PMTiles file for this area
  | 'off' // the user turned the layer off
  | 'no-selection'
  | 'too-large'
  | 'zoom-in' // selection is small enough but the map is below the tile zoom range
  | 'visible';

export interface PixelInputs {
  available: boolean;
  enabled: boolean;
  /** Area of the current selection in km2, or null for no selection. */
  areaKm2: number | null;
  zoom: number;
  maxKm2?: number;
}

/** Decide what the layer does. Order matters: missing data wins, then the user's choice. */
export function pixelState(i: PixelInputs): PixelState {
  if (!i.available) return 'unavailable';
  if (!i.enabled) return 'off';
  if (i.areaKm2 === null) return 'no-selection';
  if (i.areaKm2 > (i.maxKm2 ?? PIXEL_MAX_KM2)) return 'too-large';
  if (i.zoom < PIXEL_MIN_ZOOM) return 'zoom-in';
  return 'visible';
}

/** Plain-language note for the states that need one, else an empty string. */
export function pixelNote(state: PixelState, maxKm2 = PIXEL_MAX_KM2): string {
  switch (state) {
    case 'too-large':
      return `Pixel detail shows for selections under ${maxKm2} km². Draw a smaller area to see it.`;
    case 'zoom-in':
      return `Zoom in to see converted 30 m pixels (zoom ${PIXEL_MIN_ZOOM} and closer).`;
    case 'no-selection':
      return `Draw a shape under ${maxKm2} km² to see converted 30 m pixels.`;
    default:
      return '';
  }
}

/** MapLibre filter: one interval (baseline year) and one target. */
export function pixelFilter(intervalFrom: number, target: string): unknown[] {
  return ['all', ['==', ['get', 'interval'], intervalFrom], ['==', ['get', 'target'], target]];
}

/** Pixel colour per target, chosen to stay visible over the orange heat map and the grey basemap. */
export const PIXEL_COLOR: Record<string, string> = {
  crop: '#d62728',
  pasture: '#7b3fb0',
  urban: '#1f4fd6',
  barren: '#5a3a1a',
};

export function pixelColor(target: string): string {
  return PIXEL_COLOR[target] ?? PIXEL_COLOR.crop;
}

/** Layer id and PMTiles URL path for an area, relative to the data folder. */
export function pmtilesPath(areaId: string): string {
  return `${areaId}/converted.pmtiles`;
}
