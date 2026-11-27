import * as maplibregl from 'maplibre-gl';
import { PMTiles, Protocol } from 'pmtiles';
import 'maplibre-gl/dist/maplibre-gl.css';
import {
  TerraDraw,
  TerraDrawPolygonMode,
  TerraDrawRectangleMode,
  TerraDrawSelectMode,
  type GeoJSONStoreFeatures,
} from 'terra-draw';
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter';
import './style.css';
import { visibleAreas } from './lib/areas';
import { buildCsv } from './lib/csv';
import { loadAreas, loadCells, loadIndex, loadMeta, loadProvinceSummary, loadTiles } from './lib/data';
import { buildGrid } from './lib/grid';
import { cellsInPolygon, polygonBBox, selectionStatus, summarize, summarizeTargets } from './lib/summary';
import { DEFAULT_TARGET, targetLabel } from './lib/targets';
import {
  PIXEL_MAX_ZOOM,
  PIXEL_MIN_ZOOM,
  PIXEL_SOURCE_LAYER,
  pixelColor,
  pixelFilter,
  pixelNote,
  pixelState,
  pmtilesPath,
} from './lib/pixels';
import { buildProvinceCard, provinceCodes } from './lib/province';
import {
  cellsOfRegion,
  regionLabel,
  regionOptions,
  tilesForBBox,
  tilesForRegion,
  unionBBox,
} from './lib/tiles';
import type { AreaEntry, AreaIndex, BBox, Cells, Meta, PolygonGeometry, ProvinceSummary, Summary, TileEntry } from './lib/types';
import { polygonAreaKm2 } from './lib/geo';
import { decodeShare, encodeShare } from './lib/share';
import { ICONS, LOGO } from './icons';
import {
  renderAbout,
  renderEmpty,
  renderError,
  renderLoading,
  renderMessage,
  renderSummary,
  onIntervalPick,
  resetInterval,
  selectedInterval,
} from './render';
import { renderProvinceCard } from './renderProvince';

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const summaryEl = $('summary');
const aboutBody = $('about-body');
const hintEl = $('hint');
const csvBtn = $<HTMLButtonElement>('btn-csv');
const reportBtn = $<HTMLButtonElement>('btn-report');
const shareBtn = $<HTMLButtonElement>('btn-share');
const legendEl = $('legend');
const resultsBtn = $('btn-results');
resultsBtn.addEventListener('click', () => {
  $('panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
  $('panel').focus({ preventScroll: true });
});
const toastEl = $('toast');

$('logo').innerHTML = LOGO;
document.querySelectorAll<HTMLElement>('[data-icon]').forEach((n) => {
  n.innerHTML = ICONS[n.dataset.icon as keyof typeof ICONS] ?? '';
  n.style.display = 'inline-flex';
});

let toastTimer: number | undefined;
function toast(text: string): void {
  toastEl.textContent = text;
  toastEl.classList.add('show');
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toastEl.classList.remove('show'), 2400);
}

function zoomToArea(): void {
  if (!meta) return;
  map.fitBounds([[meta.bbox[0], meta.bbox[1]], [meta.bbox[2], meta.bbox[3]]], { padding: 30 });
}

let hintTimer: number | undefined;
function setHint(text: string, ttl = 0): void {
  hintEl.textContent = text;
  window.clearTimeout(hintTimer);
  if (text && ttl) hintTimer = window.setTimeout(() => (hintEl.textContent = ''), ttl);
}

function syncHash(poly: PolygonGeometry | null): void {
  if (!meta) return;
  history.replaceState(null, '', encodeShare(meta.area_id, poly));
}
const areaSelect = $<HTMLSelectElement>('area-select');
const modeButtons: Record<string, HTMLButtonElement> = {
  polygon: $('btn-polygon'),
  rectangle: $('btn-rect'),
  select: $('btn-edit'),
};

const HINTS: Record<string, string> = {
  polygon: 'Click to add corners. Double-click, or click the last point again, to finish. Esc cancels.',
  rectangle: 'Press on one corner, drag to the opposite corner, then release. Esc cancels.',
  select: 'Drag to move the shape, or drag a corner to reshape.',
  static: '',
};

let meta: Meta | null = null;
let cells: Cells | null = null;
let summary: Summary | null = null;
let areas: AreaEntry[] = [];
let currentPoly: PolygonGeometry | null = null;
let selectedIdx: number[] = [];
let activeTarget = DEFAULT_TARGET;
/** Tiled areas (contract version 3) only: the index, the optional province summary and the heat map cells. */
let index: AreaIndex | null = null;
let provinceSummary: ProvinceSummary | null = null;
let provinceCode = 'all';
/** Cells behind the heat map. Same as `cells` for a flat area; for a tiled area, the region or detail loaded. */
let gridCells: Cells | null = null;
let updateToken = 0;
/** Most tiles loaded for a province detail view before asking the user to pick a region. */
const MAX_DETAIL_TILES = 12;
const regionSelect = $<HTMLSelectElement>('region-select');

const pmProtocol = new Protocol();
maplibregl.addProtocol('pmtiles', pmProtocol.tile);
maplibregl.setWorkerUrl(`${import.meta.env.BASE_URL}maplibre/maplibre-gl-worker.mjs`);

const map = new maplibregl.Map({
  container: 'map',
  style: {
    version: 8,
    sources: {
      osm: {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        maxzoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
    },
    layers: [{ id: 'osm', type: 'raster', source: 'osm', paint: { 'raster-saturation': -0.45, 'raster-contrast': -0.1 } }],
  },
  attributionControl: false,
  center: [-106, 52.5],
  zoom: 8,
});
map.addControl(new maplibregl.AttributionControl({ compact: false }), 'bottom-right');
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');

let draw: TerraDraw;

function polygonFromDraw(): PolygonGeometry | null {
  const polys = draw
    .getSnapshot()
    .filter((f) => f.geometry.type === 'Polygon' && f.properties.mode !== 'select');
  const last = polys[polys.length - 1];
  return last ? (last.geometry as PolygonGeometry) : null;
}

function disableExports(): void {
  csvBtn.disabled = true;
  reportBtn.disabled = true;
  shareBtn.disabled = true;
}

function regionName(id: string): string {
  return index?.region_summary.find((r) => r.id === id)?.name ?? id;
}

function showProvinceOrEmpty(): void {
  const model = provinceSummary ? buildProvinceCard(provinceSummary, provinceCode, regionName) : null;
  if (!provinceSummary || !model) {
    renderEmpty(summaryEl);
    return;
  }
  renderProvinceCard(summaryEl, model, {
    options: provinceCodes(provinceSummary).map((c) => ({ code: c, name: c === 'all' ? 'Manitoba and Saskatchewan' : provinceSummary!.provinces[c].name })),
    onProvince: (c) => {
      provinceCode = c;
      showProvinceOrEmpty();
    },
    onDetail: (c) => void showProvinceDetail(c),
  });
}

async function update(poly: PolygonGeometry | null): Promise<void> {
  if (!meta) return;
  const token = ++updateToken;
  syncHash(poly);
  resultsBtn.hidden = !poly;
  selectionKm2 = poly ? polygonAreaKm2(poly) : null;
  if (!poly) {
    summary = null;
    refreshPixels();
    disableExports();
    showProvinceOrEmpty();
    return;
  }
  if (index) {
    // Tiled area: fetch only the tiles under the shape, then sum as for a flat area.
    const tiles = tilesForBBox(index, polygonBBox(poly));
    try {
      if (tiles.length > 0) setHint(`Loading tile data (0 of ${tiles.length})`);
      const merged = await loadTiles(meta.area_id, tiles, (d, n) => {
        if (token === updateToken) setHint(`Loading tile data (${d} of ${n})`);
      });
      if (token !== updateToken) return;
      cells = merged;
      setHint('');
    } catch (err) {
      if (token !== updateToken) return;
      setHint('');
      disableExports();
      renderError(summaryEl, `Could not load map data for this shape. ${(err as Error).message}`);
      return;
    }
  }
  if (!cells) return;
  const idx = cellsInPolygon(cells, poly);
  const status = selectionStatus(idx.length, polygonBBox(poly), meta.bbox);
  selectedIdx = idx;
  summary = summarize(cells, meta, idx, activeTarget);
  if (status === 'outside-coverage' || status === 'no-natural-cells') {
    disableExports();
    setHint('');
    renderMessage(summaryEl, status, zoomToArea);
    return;
  }
  csvBtn.disabled = false;
  reportBtn.disabled = false;
  shareBtn.disabled = false;
  currentPoly = poly;
  refreshPixels();
  renderSummary(summaryEl, summary, meta, status, { areaKm2: polygonAreaKm2(poly), poly, onTarget: setTarget });
}

function setMode(mode: string): void {
  endRectDrag(true);
  rectArmed = mode === 'rectangle';
  map.getCanvas().style.cursor = rectArmed ? 'crosshair' : '';
  // Rectangles are drawn by our own press-and-drag handler, not terra-draw's
  // click-click rectangle mode, so terra-draw stays idle while armed.
  draw.setMode(rectArmed ? 'static' : mode);
  for (const [m, b] of Object.entries(modeButtons)) b.setAttribute('aria-pressed', String(m === mode));
  setHint(HINTS[mode] ?? '', mode === 'select' ? 4000 : 0);
}

function keepOnly(id: string | number): void {
  const others = draw
    .getSnapshot()
    .filter((f) => f.id !== id && f.geometry.type === 'Polygon')
    .map((f) => f.id as string | number);
  if (others.length) draw.removeFeatures(others);
}

function clearAll(): void {
  draw.clear();
  setMode('static');
  void update(null);
}

function setupDraw(): void {
  const selectFlags = {
    feature: {
      draggable: true,
      coordinates: { midpoints: true, draggable: true, deletable: true },
    },
  };
  draw = new TerraDraw({
    adapter: new TerraDrawMapLibreGLAdapter({ map }),
    modes: [
      new TerraDrawPolygonMode(),
      new TerraDrawRectangleMode(),
      new TerraDrawSelectMode({ flags: { polygon: selectFlags, rectangle: selectFlags } }),
    ],
  });
  draw.start();
  draw.on('finish', (id, ctx) => {
    if (ctx.action === 'draw') {
      keepOnly(id);
      setMode('select');
      draw.selectFeature(id);
    }
    void update(polygonFromDraw());
  });
  draw.on('change', (_ids, type) => {
    if (type === 'update' && draw.getMode() === 'select') void update(polygonFromDraw());
    if (type === 'delete' && !polygonFromDraw() && draw.getMode() === 'select') void update(null);
  });
  modeButtons.polygon.addEventListener('click', () => setMode('polygon'));
  modeButtons.rectangle.addEventListener('click', () => setMode('rectangle'));
  modeButtons.select.addEventListener('click', () => {
    if (!polygonFromDraw()) {
      setHint('Draw a shape first, then use Edit shape.', 4000);
      return;
    }
    setMode('select');
  });
  $('btn-clear').addEventListener('click', clearAll);
  $('btn-view').addEventListener('click', useMapView);
}

let rectArmed = false;
let rectStart: maplibregl.LngLat | null = null;
let rectStartPx: { x: number; y: number } | null = null;

const emptyFc = { type: 'FeatureCollection', features: [] } as GeoJSON.FeatureCollection;

function rectCoords(a: maplibregl.LngLat, b: maplibregl.LngLat): number[][] {
  const w = Math.min(a.lng, b.lng);
  const e = Math.max(a.lng, b.lng);
  const s = Math.min(a.lat, b.lat);
  const n = Math.max(a.lat, b.lat);
  return [[w, s], [e, s], [e, n], [w, n], [w, s]];
}

function setPreview(coords: number[][] | null): void {
  const src = map.getSource('rect-preview') as maplibregl.GeoJSONSource | undefined;
  if (!src) return;
  src.setData(
    coords
      ? { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [coords] } }
      : emptyFc,
  );
}

function endRectDrag(cancel: boolean, end?: maplibregl.LngLat, endPx?: { x: number; y: number }): void {
  const start = rectStart;
  const startPx = rectStartPx;
  rectStart = null;
  rectStartPx = null;
  setPreview(null);
  map.dragPan.enable();
  if (cancel || !start || !startPx || !end || !endPx) return;
  // Ignore a stray click or tiny drag.
  if (Math.abs(endPx.x - startPx.x) < 6 || Math.abs(endPx.y - startPx.y) < 6) {
    setHint('That shape is too small. Press and drag across a larger area.', 3500);
    return;
  }
  addRectangle(rectCoords(start, end));
}

function setupRectDrag(): void {
  const px = (e: { point: { x: number; y: number } }) => ({ x: e.point.x, y: e.point.y });
  const down = (e: maplibregl.MapMouseEvent | maplibregl.MapTouchEvent) => {
    if (!rectArmed) return;
    rectStart = e.lngLat;
    rectStartPx = px(e);
    map.dragPan.disable();
  };
  const move = (e: maplibregl.MapMouseEvent | maplibregl.MapTouchEvent) => {
    if (rectStart) setPreview(rectCoords(rectStart, e.lngLat));
  };
  const up = (e: maplibregl.MapMouseEvent | maplibregl.MapTouchEvent) => {
    if (rectStart) endRectDrag(false, e.lngLat, px(e));
  };
  map.on('mousedown', down);
  map.on('touchstart', down);
  map.on('touchmove', move);
  map.on('touchend', up);
  // Track the mouse on the window so releasing over a map overlay (legend, toolbar) still ends the drag.
  const winPoint = (e: MouseEvent) => {
    const r = map.getCanvas().getBoundingClientRect();
    const point = { x: e.clientX - r.left, y: e.clientY - r.top };
    return { point, lngLat: map.unproject([point.x, point.y]) };
  };
  window.addEventListener('mousemove', (e) => {
    if (rectStart) setPreview(rectCoords(rectStart, winPoint(e).lngLat));
  });
  window.addEventListener('mouseup', (e) => {
    if (!rectStart) return;
    const w = winPoint(e);
    endRectDrag(false, w.lngLat, w.point);
  });
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && rectStart) endRectDrag(true);
  });
  map.addSource('rect-preview', { type: 'geojson', data: emptyFc });
  map.addLayer({ id: 'rect-preview-fill', type: 'fill', source: 'rect-preview', paint: { 'fill-color': '#0b5d3b', 'fill-opacity': 0.15 } });
  map.addLayer({ id: 'rect-preview-line', type: 'line', source: 'rect-preview', paint: { 'line-color': '#0b5d3b', 'line-width': 2, 'line-dasharray': [2, 1] } });
}

/** Replace any shape with this rectangle and select it for editing. */
function addRectangle(coords: number[][], mode: 'rectangle' | 'polygon' = 'rectangle'): void {
  const r = (v: number) => Math.round(v * 1e6) / 1e6; // terra-draw rejects excess precision
  draw.clear();
  const feature: GeoJSONStoreFeatures = {
    type: 'Feature',
    properties: { mode },
    geometry: { type: 'Polygon', coordinates: [coords.map(([x, y]) => [r(x), r(y)])] },
  };
  const res = draw.addFeatures([feature]);
  if (res.some((v) => !v.valid)) console.warn('addFeatures rejected', JSON.stringify(res));
  setMode('select');
  void update(polygonFromDraw());
}

/** Keyboard-friendly alternative to drawing: take the shape from the current map view. */
function useMapView(): void {
  const b = map.getBounds();
  const insetX = (b.getEast() - b.getWest()) * 0.1;
  const insetY = (b.getNorth() - b.getSouth()) * 0.1;
  const w = b.getWest() + insetX;
  const south = b.getSouth() + insetY;
  const e = b.getEast() - insetX;
  const n = b.getNorth() - insetY;
  addRectangle([[w, south], [e, south], [e, n], [w, n], [w, south]]);
}

function setGrid(visible: boolean): void {
  if (map.getLayer('grid-fill')) {
    const v = visible ? 'visible' : 'none';
    map.setLayoutProperty('grid-fill', 'visibility', v);
    map.setLayoutProperty('grid-line', 'visibility', v);
  }
  legendEl.hidden = !visible;
}

function setupGridLayers(): void {
  map.addSource('grid', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({
    id: 'grid-fill',
    type: 'fill',
    source: 'grid',
    paint: {
      'fill-color': ['interpolate', ['linear'], ['get', 'conv'], 0, '#ffe08a', 5, '#f4a259', 20, '#e0702f', 50, '#b13a0b'],
      'fill-opacity': ['case', ['>', ['get', 'conv'], 0], 0.62, 0.06],
    },
  });
  map.addLayer({
    id: 'grid-line',
    type: 'line',
    source: 'grid',
    paint: { 'line-color': '#6b4f1d', 'line-opacity': 0.2, 'line-width': 0.5 },
  });
}

function setLegendTitle(): void {
  if (!meta) return;
  const first = meta.intervals[0];
  if (!first) return;
  const what = activeTarget === DEFAULT_TARGET ? '' : ` to ${targetLabel(activeTarget)}`;
  $('legend-title').textContent = `Converted ha per cell${what}, ${first.from} to ${first.to}`;
}

/** Switch the active conversion target: reshade the map, then recompute and redraw the summary. */
function setTarget(target: string): void {
  if (!meta || (!cells && !index) || target === activeTarget) return;
  activeTarget = target;
  if (gridCells) (map.getSource('grid') as maplibregl.GeoJSONSource).setData(buildGrid(gridCells, meta, activeTarget).data);
  setLegendTitle();
  refreshPixels();
  void update(currentPoly);
}

/** 30 m converted-pixel layer (ADR 0003). Needs a PMTiles file per area; absent today on the live site. */
const PIXEL_SRC = 'pixels';
const PIXEL_LYR = 'pixels-fill';
let pixelsAvailable = false;
let selectionKm2: number | null = null;
let pixelToken = 0;
const pixelSwitch = $('pixel-switch');
const pixelChk = $<HTMLInputElement>('chk-pixels');
const pixelNoteEl = $('pixel-note');
const pixelLegend = $('pixel-legend');

function removePixelLayer(): void {
  if (map.getLayer(PIXEL_LYR)) map.removeLayer(PIXEL_LYR);
  if (map.getSource(PIXEL_SRC)) map.removeSource(PIXEL_SRC);
}

/** Probe for the area's PMTiles file and add the layer if it is a real archive. Any failure means no layer. */
async function setupPixels(areaId: string): Promise<void> {
  const token = ++pixelToken;
  pixelsAvailable = false;
  removePixelLayer();
  try {
    const url = new URL(`${import.meta.env.BASE_URL}data/${pmtilesPath(areaId)}`, location.href).href;
    const archive = new PMTiles(url);
    await archive.getHeader(); // throws for a missing file or an HTML fallback page
    if (token !== pixelToken) return;
    pmProtocol.add(archive);
    map.addSource(PIXEL_SRC, {
      type: 'vector',
      url: `pmtiles://${url}`,
      minzoom: PIXEL_MIN_ZOOM,
      maxzoom: PIXEL_MAX_ZOOM,
    });
    map.addLayer({
      id: PIXEL_LYR,
      type: 'fill',
      source: PIXEL_SRC,
      'source-layer': PIXEL_SOURCE_LAYER,
      minzoom: PIXEL_MIN_ZOOM,
      layout: { visibility: 'none' },
      paint: { 'fill-color': pixelColor(activeTarget), 'fill-opacity': 0.85, 'fill-antialias': false },
    });
    pixelsAvailable = true;
  } catch {
    pixelsAvailable = false;
  }
  refreshPixels();
}

/** Apply the current target, interval, selection size and toggle to the pixel layer, legend and note. */
function refreshPixels(): void {
  pixelSwitch.hidden = !pixelsAvailable;
  const state = pixelState({
    available: pixelsAvailable,
    enabled: pixelChk.checked,
    areaKm2: selectionKm2,
    zoom: map.getZoom(),
  });
  const note = pixelNote(state);
  pixelNoteEl.textContent = note;
  pixelNoteEl.hidden = !note;
  const visible = state === 'visible';
  pixelLegend.hidden = !visible;
  if (!pixelsAvailable || !map.getLayer(PIXEL_LYR)) return;
  map.setLayoutProperty(PIXEL_LYR, 'visibility', visible ? 'visible' : 'none');
  if (!visible || !meta) return;
  const iv = meta.intervals[selectedInterval()] ?? meta.intervals[0];
  if (iv) map.setFilter(PIXEL_LYR, pixelFilter(iv.from, activeTarget) as maplibregl.FilterSpecification);
  const color = pixelColor(activeTarget);
  map.setPaintProperty(PIXEL_LYR, 'fill-color', color);
  $('pixel-swatch').style.background = color;
  $('pixel-legend-text').textContent =
    `${targetLabel(activeTarget)}, ${iv ? `${iv.from} to ${iv.to}` : ''}. Pixel detail; totals use the 1 km grid.`;
}

const emptyGrid = { type: 'FeatureCollection', features: [] } as GeoJSON.FeatureCollection;

function fitBox(box: BBox, duration = 0): void {
  map.fitBounds([[box[0], box[1]], [box[2], box[3]]], { padding: 30, duration });
}

function showGrid(c: Cells | null): void {
  if (!meta) return;
  gridCells = c;
  const src = map.getSource('grid') as maplibregl.GeoJSONSource;
  if (!c) {
    src.setData(emptyGrid);
    return;
  }
  const grid = buildGrid(c, meta, activeTarget);
  src.setData(grid.data);
  if (grid.drawn < grid.total) {
    setHint(`Grid overlay thinned to ${grid.drawn} of ${grid.total} cells for speed. Summaries use every cell.`, 6000);
  }
}

/** Load tiles for the heat map and zoom to them. Stale loads (the user moved on) are dropped. */
let detailToken = 0;
async function loadDetail(tiles: TileEntry[], keep?: (c: Cells) => Cells): Promise<void> {
  if (!meta || !index || tiles.length === 0) return;
  const token = ++detailToken;
  try {
    setHint(`Loading tile data (0 of ${tiles.length})`);
    let c = await loadTiles(meta.area_id, tiles, (d, n) => {
      if (token === detailToken) setHint(`Loading tile data (${d} of ${n})`);
    });
    if (token !== detailToken) return;
    if (keep) c = keep(c);
    setHint('');
    showGrid(c);
    const box = unionBBox(tiles);
    if (box) fitBox(box, 400);
  } catch (err) {
    if (token !== detailToken) return;
    setHint('');
    renderError(summaryEl, `Could not load map data. ${(err as Error).message}`);
  }
}

async function pickRegion(regionId: string): Promise<void> {
  if (!index) return;
  if (!regionId) {
    detailToken++;
    showGrid(null);
    if (meta) fitBox(meta.bbox, 400);
    return;
  }
  const idx = index;
  await loadDetail(tilesForRegion(idx, regionId), (c) => cellsOfRegion(c, idx, regionId));
}

async function showProvinceDetail(code: string): Promise<void> {
  if (!index || !provinceSummary) return;
  const entry = provinceSummary.provinces[code];
  const ids = entry ? entry.regions.filter((r) => provinceSummary!.coverage.regions_run.includes(r)) : [];
  const want = new Set(ids.flatMap((r) => tilesForRegion(index!, r).map((t) => t.id)));
  const tiles = index.tiles.filter((t) => want.has(t.id));
  if (tiles.length > MAX_DETAIL_TILES) {
    setHint(`That is ${tiles.length} tiles. Pick one region from the region list to load map detail.`, 6000);
    return;
  }
  regionSelect.value = '';
  await loadDetail(tiles);
}

async function loadArea(id: string): Promise<void> {
  renderLoading(summaryEl);
  index = null;
  provinceSummary = null;
  cells = null;
  gridCells = null;
  detailToken++;
  $('region-pick-wrap').hidden = true;
  try {
    meta = await loadMeta(id);
    if (meta.tiled) {
      index = await loadIndex(id);
      if (!index) throw new Error('This area is tiled but its index.json could not be read.');
      provinceSummary = await loadProvinceSummary(id);
    } else {
      cells = await loadCells(id);
    }
  } catch (err) {
    meta = null;
    cells = null;
    index = null;
    renderError(summaryEl, `Could not load data for this area. ${(err as Error).message}`);
    return;
  }
  draw.clear();
  setMode('static');
  resetInterval();
  activeTarget = DEFAULT_TARGET;
  renderAbout(aboutBody, meta);
  if (index) {
    regionSelect.replaceChildren(new Option('All regions (summary)', ''));
    for (const r of regionOptions(index)) regionSelect.append(new Option(regionLabel(r), r.id));
    regionSelect.value = '';
    $('region-pick-wrap').hidden = false;
    provinceCode = provinceSummary && provinceCodes(provinceSummary).includes('all') ? 'all' : (provinceSummary ? provinceCodes(provinceSummary)[0] : 'all');
    showGrid(null);
    fitBox(meta.bbox);
  } else if (cells) {
    showGrid(cells);
    fitBox(meta.bbox);
  }
  setLegendTitle();
  void setupPixels(id);
  void update(null);
}

shareBtn.addEventListener('click', async () => {
  const url = location.href;
  try {
    await navigator.clipboard.writeText(url);
    toast('Link copied');
  } catch {
    window.prompt('Copy this link', url);
  }
});

function download(data: string | Blob, type: string, name: string): void {
  const blob = typeof data === 'string' ? new Blob([data], { type }) : data;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}

csvBtn.addEventListener('click', () => {
  if (!summary || !meta || !cells) return;
  download(buildCsv(summarizeTargets(cells, meta, selectedIdx), meta, selectedIdx.length), 'text/csv;charset=utf-8', `conversion-summary-${meta.area_id}.csv`);
});

reportBtn.addEventListener('click', async () => {
  if (!summary || !meta || !cells || !currentPoly) return;
  const input = {
    summaries: summarizeTargets(cells, meta, selectedIdx),
    meta,
    poly: currentPoly,
    areaKm2: polygonAreaKm2(currentPoly),
    url: location.href,
    generatedAt: new Date().toISOString(),
  };
  const name = `conversion-report-${meta.area_id}.docx`;
  reportBtn.disabled = true;
  try {
    const { reportDocx } = await import('./lib/reportDocx');
    download(await reportDocx(input), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', name);
  } catch (err) {
    renderError(summaryEl, `Could not make the Word report. ${(err as Error).message}`);
  } finally {
    reportBtn.disabled = false;
  }
});

$<HTMLInputElement>('chk-grid').addEventListener('change', (e) =>
  setGrid((e.target as HTMLInputElement).checked),
);

pixelChk.addEventListener('change', refreshPixels);
onIntervalPick(refreshPixels);
map.on('zoomend', refreshPixels);

areaSelect.addEventListener('change', () => void loadArea(areaSelect.value));
regionSelect.addEventListener('change', () => void pickRegion(regionSelect.value));

renderLoading(summaryEl);

map.on('load', async () => {
  setupGridLayers();
  setupDraw();
  setupRectDrag();
  try {
    areas = visibleAreas(await loadAreas());
  } catch (err) {
    renderError(summaryEl, `Could not load the list of areas. ${(err as Error).message}`);
    return;
  }
  if (areas.length === 0) {
    renderError(summaryEl, 'No data areas are available yet.');
    return;
  }
  for (const a of areas) areaSelect.append(new Option(a.name, a.id));
  $('area-pick-wrap').hidden = areas.length < 2;
  const shared = decodeShare(location.hash);
  const start = areas.find((a) => a.id === shared.area) ?? areas[0];
  areaSelect.value = start.id;
  await loadArea(start.id);
  if (shared.poly && meta) {
    const ring = shared.poly.coordinates[0];
    addRectangle(ring, ring.length === 5 ? 'rectangle' : 'polygon');
  }
  document.body.dataset.ready = 'true';
});

// Test hook for automated browser checks.
(window as unknown as { __map: maplibregl.Map }).__map = map;
