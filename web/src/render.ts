import { cap, fmtHa, fmtPct } from './lib/format';
import { MIN_RELIABLE_CELLS, type SelectionStatus } from './lib/summary';
import type { Meta, Summary } from './lib/types';

// Colour-blind safe hues; bars are also labelled directly, so colour is not the only cue.
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

export function renderEmpty(root: HTMLElement): void {
  root.replaceChildren(
    el('h2', 'Summary'),
    el(
      'p',
      'Draw a polygon or rectangle on the map to see how much natural habitat was converted to cropland inside it.',
    ),
  );
}

export function renderMessage(root: HTMLElement, status: SelectionStatus): void {
  const msg =
    status === 'outside-coverage'
      ? 'The selected area is outside the data coverage for this region. Move the shape onto the shaded study area, or pick another area.'
      : 'No cells with natural cover were found in the selected area, so there is nothing to summarize. Try a larger shape, or turn on the data grid to see where data exists.';
  root.replaceChildren(el('h2', 'Summary'), note(msg, 'warn'));
}

export function renderSummary(
  root: HTMLElement,
  summary: Summary,
  meta: Meta,
  status: SelectionStatus,
): void {
  const nodes: Node[] = [el('h2', 'Summary')];
  const n = summary.cellCount;
  nodes.push(
    el(
      'p',
      `${n} grid cell${n === 1 ? '' : 's'} (about ${(meta.cell_size_m / 1000) ** 2} km² each) with natural cover selected. ` +
        'Hectares are rounded and approximate.',
      'sub',
    ),
  );
  if (status === 'few-cells') {
    nodes.push(
      note(
        `Only ${n} cell${n === 1 ? '' : 's'} selected (fewer than ${MIN_RELIABLE_CELLS}). Results for very small areas carry high uncertainty. Treat them as indicative only.`,
        'warn',
      ),
    );
  }

  for (const iv of summary.intervals) {
    const wrap = el('section', undefined, 'interval');
    const h = el('h3', `${iv.from} to ${iv.to}`);
    h.append(el('span', ` (${iv.years} years)`, 'muted'));
    wrap.append(h);
    const table = el('table');
    const caption = el('caption', `Conversion of natural habitat to crop, ${iv.from} to ${iv.to}`, 'sr-only');
    const thead = el('thead');
    const hr = el('tr');
    for (const [label, num] of [
      ['Class', false],
      [`Natural ha in ${iv.from}`, true],
      ['Converted ha', true],
      ['% converted', true],
      ['ha per year', true],
    ] as const) {
      const th = el('th', label, num ? 'num' : undefined);
      th.scope = 'col';
      hr.append(th);
    }
    thead.append(hr);
    const tbody = el('tbody');
    for (const r of [...iv.rows, iv.total]) {
      const tr = el('tr', undefined, r.cls === 'total' ? 'total' : undefined);
      const th = el('th', cap(r.cls));
      th.scope = 'row';
      tr.append(
        th,
        el('td', fmtHa(r.naturalHa), 'num'),
        el('td', fmtHa(r.convertedHa), 'num'),
        el('td', fmtPct(r.percent), 'num'),
        el('td', fmtHa(r.ratePerYear), 'num'),
      );
      tbody.append(tr);
    }
    table.append(caption, thead, tbody);
    wrap.append(table);
    nodes.push(wrap);
  }

  nodes.push(renderChart(summary));
  root.replaceChildren(...nodes);
}

function renderChart(summary: Summary): HTMLElement {
  const fig = el('figure', undefined, 'chart');
  fig.append(el('figcaption', 'Converted hectares by class and interval'));
  const max = Math.max(
    0.0001,
    ...summary.intervals.flatMap((iv) => iv.rows.map((r) => r.convertedHa)),
  );
  for (const iv of summary.intervals) {
    const group = el('div', undefined, 'bar-group');
    group.append(el('div', `${iv.from} to ${iv.to}`, 'bar-title'));
    for (const r of iv.rows) {
      const row = el('div', undefined, 'bar-row');
      row.append(el('span', cap(r.cls), 'bar-label'));
      const track = el('span', undefined, 'bar-track');
      const bar = el('span', undefined, 'bar');
      bar.style.width = `${(r.convertedHa / max) * 100}%`;
      bar.style.background = CLASS_COLOR[r.cls] ?? '#555';
      track.append(bar);
      row.append(track, el('span', `${fmtHa(r.convertedHa)} ha`, 'bar-val'));
      group.append(row);
    }
    fig.append(group);
  }
  fig.setAttribute('role', 'img');
  fig.setAttribute(
    'aria-label',
    'Bar chart of converted hectares by natural class for each interval. The same values are in the tables above.',
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
