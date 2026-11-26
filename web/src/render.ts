import { cap, fmtHa, fmtPct } from './lib/format';
import { MIN_RELIABLE_CELLS, type SelectionStatus } from './lib/summary';
import { coordinatesText, polygonVertices } from './lib/report';
import type { IntervalSummary, Meta, PolygonGeometry, Summary } from './lib/types';

// Colour-blind safe hues; rows and bars are also labelled directly, so colour is not the only cue.
const CLASS_COLOR: Record<string, string> = {
  forest: '#1b7f5c',
  grassland: '#b8860b',
  wetland: '#1f6fb2',
  shrubland: '#a64d79',
};

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  text?: string,
  cls?: string,
): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}

function note(text: string, kind: 'warn' | 'info'): HTMLElement {
  const p = el('p', text, `note ${kind}`);
  p.setAttribute('role', 'status');
  return p;
}

export function renderLoading(root: HTMLElement): void {
  root.innerHTML =
    '<div class="skeleton" aria-hidden="true"><i style="height:28px;width:55%"></i><i style="height:120px"></i><i style="height:180px"></i></div><p class="sr-only">Loading data</p>';
}

export function renderEmpty(root: HTMLElement): void {
  const wrap = el('div', undefined, 'empty');
  wrap.append(
    el('h2', 'Select an area'),
    el(
      'p',
      'See how much forest, grassland, wetland and shrubland became cropland inside any shape you draw.',
      'lead',
    ),
  );
  const ol = el('ol', undefined, 'steps');
  for (const [title, body] of [
    ['Draw on the map', 'Use Polygon or Rectangle, or frame an area and choose Map view.'],
    ['Read the summary', 'Hectares and percent of natural habitat converted, by interval.'],
    ['Export or share', 'Download a CSV or a methods and results report, or copy a link that reopens your shape.'],
  ]) {
    const li = el('li');
    const d = el('div');
    d.append(el('strong', title), el('span', body));
    li.append(d);
    ol.append(li);
  }
  wrap.append(ol);
  root.replaceChildren(wrap);
}

export function renderMessage(root: HTMLElement, status: SelectionStatus, onZoom?: () => void): void {
  const msg =
    status === 'outside-coverage'
      ? 'This shape is outside the study area. Zoom to the study area, then draw again.'
      : 'No cells with natural cover were found in the selected area, so there is nothing to summarize. Try a larger shape, or turn on the heat map to see where data exists.';
  const nodes: Node[] = [el('h2', 'Summary'), note(msg, 'warn')];
  if (status === 'outside-coverage' && onZoom) {
    const b = el('button', 'Zoom to study area', 'linkbtn');
    b.type = 'button';
    b.addEventListener('click', onZoom);
    nodes.push(b);
  }
  root.replaceChildren(...nodes);
}

export function renderError(root: HTMLElement, text: string): void {
  root.replaceChildren(el('h2', 'Something went wrong'), note(text, 'warn'));
}

export interface SelectionInfo {
  areaKm2: number;
  poly: PolygonGeometry;
}

let selected = 0;
let last: { root: HTMLElement; summary: Summary; meta: Meta; status: SelectionStatus; info: SelectionInfo } | null =
  null;

export function resetInterval(): void {
  selected = 0;
}

function fmtKm2(v: number): string {
  return v >= 100 ? Math.round(v).toLocaleString('en-CA') : v.toLocaleString('en-CA', { maximumFractionDigits: 1 });
}

export function renderSummary(
  root: HTMLElement,
  summary: Summary,
  meta: Meta,
  status: SelectionStatus,
  info: SelectionInfo,
): void {
  last = { root, summary, meta, status, info };
  if (selected >= summary.intervals.length) selected = 0;
  const iv = summary.intervals[selected];
  const n = summary.cellCount;
  const nodes: Node[] = [el('h2', 'Summary')];

  const chips = el('ul', undefined, 'chips');
  for (const [k, v] of [
    ['Area', `${fmtKm2(info.areaKm2)} km²`],
    ['Cells', String(n)],
  ]) {
    const li = el('li', undefined, 'chip');
    li.append(`${k} `, el('b', v));
    chips.append(li);
  }
  nodes.push(chips);

  if (status === 'few-cells') {
    nodes.push(
      note(
        `Only ${n} cell${n === 1 ? '' : 's'} selected (fewer than ${MIN_RELIABLE_CELLS}). Results for very small areas carry high uncertainty. Treat them as indicative only.`,
        'warn',
      ),
    );
  }

  nodes.push(renderTabs(summary));
  const panel = el('div');
  panel.id = 'tabpanel';
  panel.setAttribute('role', 'tabpanel');
  panel.setAttribute('aria-labelledby', `tab-${selected}`);
  panel.append(
    renderHero(iv),
    renderClasses(iv),
    renderChart(iv),
    el(
      'p',
      `Each cell is about ${(meta.cell_size_m / 1000) ** 2} km². A cell is counted when its centre falls inside your shape. Hectares are rounded and approximate.`,
      'small',
    ),
  );
  nodes.push(panel);
  nodes.push(renderCoordinates(info.poly));
  root.replaceChildren(...nodes);
}

function renderCoordinates(poly: PolygonGeometry): HTMLElement {
  const d = el('details', undefined, 'coords');
  const n = polygonVertices(poly).length;
  d.append(el('summary', `Selection coordinates (${n} vertices)`));
  d.append(
    el('p', 'WGS84, latitude then longitude, in order around the shape. Quote these to state exactly which area was summarized.', 'small'),
  );
  const text = coordinatesText(poly);
  d.append(el('pre', text));
  const b = el('button', 'Copy coordinates', 'linkbtn');
  b.type = 'button';
  b.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(text);
      b.textContent = 'Copied';
    } catch {
      b.textContent = 'Copy failed, select the text above';
    }
  });
  d.append(b);
  return d;
}

function renderTabs(summary: Summary): HTMLElement {
  const tabs = el('div', undefined, 'tabs');
  tabs.setAttribute('role', 'tablist');
  tabs.setAttribute('aria-label', 'Time interval');
  summary.intervals.forEach((iv, i) => {
    const b = el('button', `${iv.from} to ${iv.to}`);
    b.type = 'button';
    b.setAttribute('role', 'tab');
    b.id = `tab-${i}`;
    b.setAttribute('aria-controls', 'tabpanel');
    b.setAttribute('aria-selected', String(i === selected));
    b.tabIndex = i === selected ? 0 : -1;
    b.addEventListener('click', () => pick(i));
    b.addEventListener('keydown', (e) => {
      const L = summary.intervals.length;
      let next = -1;
      if (e.key === 'ArrowRight') next = (i + 1) % L;
      else if (e.key === 'ArrowLeft') next = (i - 1 + L) % L;
      else if (e.key === 'Home') next = 0;
      else if (e.key === 'End') next = L - 1;
      if (next < 0) return;
      e.preventDefault();
      pick(next);
      (last?.root.querySelectorAll('[role=tab]')[next] as HTMLElement | undefined)?.focus();
    });
    tabs.append(b);
  });
  return tabs;
}

function pick(i: number): void {
  if (!last) return;
  selected = i;
  renderSummary(last.root, last.summary, last.meta, last.status, last.info);
}

function kpi(value: string, label: string): HTMLElement {
  const d = el('div', undefined, 'kpi');
  d.append(el('div', value, 'v'), el('div', label, 'l'));
  return d;
}

function renderHero(iv: IntervalSummary): HTMLElement {
  const t = iv.total;
  const hero = el('section', undefined, 'hero');
  hero.setAttribute('aria-label', `Headline result, ${iv.from} to ${iv.to}`);
  hero.append(el('div', 'Habitat converted to cropland', 'eyebrow'));
  const big = el('div', undefined, 'big');
  big.append(fmtHa(t.convertedHa), el('small', ' ha'));
  hero.append(big);
  const base = el(
    'div',
    `${fmtPct(t.percent)} of the ${fmtHa(t.naturalHa)} ha of natural cover in ${iv.from}`,
  );
  base.className = 'sub';
  base.style.margin = '0';
  hero.append(base);
  const k = el('div', undefined, 'kpis');
  k.append(kpi(`${fmtHa(t.ratePerYear)} ha`, 'per year on average'), kpi(`${iv.years} years`, `${iv.from} to ${iv.to}`));
  hero.append(k);
  return hero;
}

function renderClasses(iv: IntervalSummary): HTMLElement {
  const sec = el('section');
  const head = el('div', undefined, 'section-head');
  head.append(el('h3', 'By natural class'), el('span', 'Indicative', 'badge'));
  sec.append(head);
  const table = el('table', undefined, 'indicative');
  table.append(
    el('caption', `Conversion of natural habitat to crop by class, ${iv.from} to ${iv.to}. Natural and Converted are in hectares; Share is percent.`, 'sr-only'),
  );
  const thead = el('thead');
  const hr = el('tr');
  for (const [label, num] of [
    ['Class', false],
    ['Natural', true],
    ['Converted', true],
    ['Share', true],
  ] as const) {
    const th = el('th', label, num ? 'num' : undefined);
    th.scope = 'col';
    hr.append(th);
  }
  thead.append(hr);
  const tbody = el('tbody');
  for (const r of [...iv.rows, iv.total]) {
    const tr = el('tr', undefined, r.cls === 'total' ? 'total' : undefined);
    const th = el('th');
    th.scope = 'row';
    if (r.cls !== 'total') {
      const sw = el('span', undefined, 'swatch');
      sw.style.background = CLASS_COLOR[r.cls] ?? '#555';
      th.append(sw);
    }
    th.append(cap(r.cls));
    tr.append(
      th,
      el('td', r.naturalHa > 0 ? fmtHa(r.naturalHa) : '-', 'num'),
      el('td', r.naturalHa > 0 ? fmtHa(r.convertedHa) : '-', 'num'),
      el('td', fmtPct(r.percent), 'num'),
    );
    tbody.append(tr);
  }
  table.append(thead, tbody);
  sec.append(table);
  sec.append(
    el(
      'p',
      'Hectares, with share as percent of natural cover in the baseline year. Class labels shift between Annual Crop Inventory years, so the split by class is indicative. The total is the more reliable figure.',
      'small',
    ),
  );
  return sec;
}

function renderChart(iv: IntervalSummary): HTMLElement {
  const fig = el('figure', undefined, 'chart');
  const max = Math.max(0.0001, ...iv.rows.map((r) => r.convertedHa));
  for (const r of iv.rows) {
    const row = el('div', undefined, 'bar-row');
    row.append(el('span', cap(r.cls), 'bar-label'));
    const track = el('span', undefined, 'bar-track');
    const bar = el('span', undefined, 'bar');
    bar.style.width = `${(r.convertedHa / max) * 100}%`;
    bar.style.background = CLASS_COLOR[r.cls] ?? '#555';
    track.append(bar);
    row.append(track, el('span', `${fmtHa(r.convertedHa)} ha`, 'bar-val'));
    fig.append(row);
  }
  fig.setAttribute('role', 'img');
  fig.setAttribute(
    'aria-label',
    `Bar chart of converted hectares by natural class, ${iv.from} to ${iv.to}. The same values are in the table above.`,
  );
  return fig;
}

export function renderAbout(root: HTMLElement, meta: Meta): void {
  const nodes: Node[] = [];
  nodes.push(
    note(
      'This is a screening tool, not a parcel-level or legal record. Results are approximate at the 1 km cell scale: a cell is counted when its centre falls inside your shape.',
      'info',
    ),
  );
  nodes.push(el('h3', meta.name));
  const dl = el('dl');
  const add = (k: string, v: string) => dl.append(el('dt', k), el('dd', v));
  add('Method', meta.method);
  add('Source', meta.source);
  add('Snapshots', meta.snapshots.join(', '));
  add('Generated', meta.generated);
  nodes.push(dl);
  if (meta.caveats.length) {
    nodes.push(el('h3', 'Caveats'));
    const ul = el('ul');
    for (const c of meta.caveats) ul.append(el('li', c));
    nodes.push(ul);
  }
  root.replaceChildren(...nodes);
}
