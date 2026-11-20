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
import { renderAbout, renderEmpty, renderMessage, renderSummary } from './render';

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const summaryEl = $('summary');
const aboutBody = $('about-body');
const hintEl = $('hint');
const csvBtn = $<HTMLButtonElement>('btn-csv');
const areaSelect = $<HTMLSelectElement>('area-select');
const modeButtons: Record<string, HTMLButtonElement> = {
  polygon: $('btn-polygon'),
  rectangle: $('btn-rect'),
  select: $('btn-edit'),
};

const HINTS: Record<string, string> = {
  polygon: 'Click to add corners. Double-click, or click the last point again, to finish. Esc cancels.',
  rectangle: 'Press on one corner, drag to the opposite corner, then release. Esc cancels.',
  select: 'Drag the shape to move it, or drag a corner to reshape it.',
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
    layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
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
  if (!poly) {
    summary = null;
    csvBtn.disabled = true;
    renderEmpty(summaryEl);
    return;
  }
  const idx = cellsInPolygon(cells, poly);
  const status = selectionStatus(idx.length, polygonBBox(poly), meta.bbox);
  summary = summarize(cells, meta, idx);
  if (status === 'outside-coverage' || status === 'no-natural-cells') {
    csvBtn.disabled = true;
    renderMessage(summaryEl, status);
    return;
  }
  csvBtn.disabled = false;
  renderSummary(summaryEl, summary, meta, status);
}

function setMode(mode: string): void {
  endRectDrag(true);
  rectArmed = mode === 'rectangle';
  map.getCanvas().style.cursor = rectArmed ? 'crosshair' : '';
  // Rectangles are drawn by our own press-and-drag handler, not terra-draw's
  // click-click rectangle mode, so terra-draw stays idle while armed.
  draw.setMode(rectArmed ? 'static' : mode);
  for (const [m, b] of Object.entries(modeButtons)) b.setAttribute('aria-pressed', String(m === mode));
  hintEl.textContent = HINTS[mode] ?? '';
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
      hintEl.textContent = 'Draw a shape first, then use Edit shape.';
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
  if (Math.abs(endPx.x - startPx.x) < 6 || Math.abs(endPx.y - startPx.y) < 6) return;
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
  map.on('mousemove', move);
  map.on('touchmove', move);
  map.on('mouseup', up);
  map.on('touchend', up);
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && rectStart) endRectDrag(true);
  });
  map.addSource('rect-preview', { type: 'geojson', data: emptyFc });
  map.addLayer({ id: 'rect-preview-fill', type: 'fill', source: 'rect-preview', paint: { 'fill-color': '#1d6fa5', 'fill-opacity': 0.15 } });
  map.addLayer({ id: 'rect-preview-line', type: 'line', source: 'rect-preview', paint: { 'line-color': '#1d6fa5', 'line-width': 2, 'line-dasharray': [2, 1] } });
}

/** Replace any shape with this rectangle and select it for editing. */
function addRectangle(coords: number[][]): void {
  const r = (v: number) => Math.round(v * 1e6) / 1e6; // terra-draw rejects excess precision
  draw.clear();
  const feature: GeoJSONStoreFeatures = {
    type: 'Feature',
    properties: { mode: 'rectangle' },
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
}

function setupGridLayers(): void {
  map.addSource('grid', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({
    id: 'grid-fill',
    type: 'fill',
    source: 'grid',
    layout: { visibility: 'none' },
    paint: {
      'fill-color': ['interpolate', ['linear'], ['get', 'conv'], 0, '#fff3b0', 10, '#f4a259', 40, '#c1440e'],
      'fill-opacity': 0.35,
    },
  });
  map.addLayer({
    id: 'grid-line',
    type: 'line',
    source: 'grid',
    layout: { visibility: 'none' },
    paint: { 'line-color': '#6b4f1d', 'line-opacity': 0.25, 'line-width': 0.5 },
  });
}

async function loadArea(id: string): Promise<void> {
  summaryEl.replaceChildren();
  summaryEl.textContent = 'Loading data...';
  try {
    [meta, cells] = await Promise.all([loadMeta(id), loadCells(id)]);
  } catch (err) {
    meta = null;
    cells = null;
    summaryEl.textContent = `Could not load data for this area. ${(err as Error).message}`;
    return;
  }
  draw.clear();
  setMode('static');
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
    hintEl.textContent = `Grid overlay thinned to ${grid.drawn} of ${grid.total} cells for speed. Summaries use every cell.`;
  }
  update(null);
}

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

map.on('load', async () => {
  setupGridLayers();
  setupDraw();
  setupRectDrag();
  try {
    areas = visibleAreas(await loadAreas());
  } catch (err) {
    summaryEl.textContent = `Could not load the list of areas. ${(err as Error).message}`;
    return;
  }
  if (areas.length === 0) {
    summaryEl.textContent = 'No data areas are available yet.';
    return;
  }
  for (const a of areas) areaSelect.append(new Option(a.name, a.id));
  $('area-pick-wrap').hidden = areas.length < 2;
  await loadArea(areas[0].id);
  document.body.dataset.ready = 'true';
});

// Test hook for automated browser checks.
(window as unknown as { __map: maplibregl.Map }).__map = map;
