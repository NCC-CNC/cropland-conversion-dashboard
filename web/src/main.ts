import * as maplibregl from 'maplibre-gl';
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
import { loadAreas, loadCells, loadMeta } from './lib/data';
import { buildGrid } from './lib/grid';
import { cellsInPolygon, polygonBBox, selectionStatus, summarize } from './lib/summary';
import type { AreaEntry, Cells, Meta, PolygonGeometry, Summary } from './lib/types';
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
  resetInterval,
} from './render';

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const summaryEl = $('summary');
const aboutBody = $('about-body');
const hintEl = $('hint');
const csvBtn = $<HTMLButtonElement>('btn-csv');
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
  select: 'Drag the shape to move it, or drag a corner to reshape.',
  static: '',
};

let meta: Meta | null = null;
let cells: Cells | null = null;
let summary: Summary | null = null;
let areas: AreaEntry[] = [];

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
  center: [-106, 52.5],
  zoom: 8,
});
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

function update(poly: PolygonGeometry | null): void {
  if (!meta || !cells) return;
  syncHash(poly);
  resultsBtn.hidden = !poly;
  if (!poly) {
    summary = null;
    csvBtn.disabled = true;
    shareBtn.disabled = true;
    renderEmpty(summaryEl);
    return;
  }
  const idx = cellsInPolygon(cells, poly);
  const status = selectionStatus(idx.length, polygonBBox(poly), meta.bbox);
  summary = summarize(cells, meta, idx);
  if (status === 'outside-coverage' || status === 'no-natural-cells') {
    csvBtn.disabled = true;
    shareBtn.disabled = true;
    setHint('');
    renderMessage(summaryEl, status, zoomToArea);
    return;
  }
  csvBtn.disabled = false;
  shareBtn.disabled = false;
  renderSummary(summaryEl, summary, meta, status, { areaKm2: polygonAreaKm2(poly) });
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
  update(null);
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
    update(polygonFromDraw());
  });
  draw.on('change', (_ids, type) => {
    if (type === 'update' && draw.getMode() === 'select') update(polygonFromDraw());
    if (type === 'delete' && !polygonFromDraw() && draw.getMode() === 'select') update(null);
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
  update(polygonFromDraw());
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

async function loadArea(id: string): Promise<void> {
  renderLoading(summaryEl);
  try {
    [meta, cells] = await Promise.all([loadMeta(id), loadCells(id)]);
  } catch (err) {
    meta = null;
    cells = null;
    renderError(summaryEl, `Could not load data for this area. ${(err as Error).message}`);
    return;
  }
  draw.clear();
  setMode('static');
  resetInterval();
  renderAbout(aboutBody, meta);
  const grid = buildGrid(cells, meta);
  (map.getSource('grid') as maplibregl.GeoJSONSource).setData(grid.data);
  map.fitBounds(
    [
      [meta.bbox[0], meta.bbox[1]],
      [meta.bbox[2], meta.bbox[3]],
    ],
    { padding: 30, duration: 0 },
  );
  if (grid.drawn < grid.total) {
    setHint(`Grid overlay thinned to ${grid.drawn} of ${grid.total} cells for speed. Summaries use every cell.`, 6000);
  }
  const legendTitle = $('legend-title');
  const first = meta.intervals[0];
  if (first) legendTitle.textContent = `Converted ha per cell, ${first.from} to ${first.to}`;
  update(null);
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

csvBtn.addEventListener('click', () => {
  if (!summary || !meta) return;
  const blob = new Blob([buildCsv(summary, meta)], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `conversion-summary-${meta.area_id}.csv`;
  document.body.append(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
});

$<HTMLInputElement>('chk-grid').addEventListener('change', (e) =>
  setGrid((e.target as HTMLInputElement).checked),
);

areaSelect.addEventListener('change', () => void loadArea(areaSelect.value));

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
