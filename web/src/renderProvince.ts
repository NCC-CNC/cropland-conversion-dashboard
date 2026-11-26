import { fmtHa, fmtPct } from './lib/format';
import type { ProvinceCardModel } from './lib/province';
import { targetShort } from './lib/targets';

function el<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string, cls?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}

export interface ProvinceCardHandlers {
  /** Province codes offered in the picker, with display names. */
  options: { code: string; name: string }[];
  onProvince: (code: string) => void;
  /** Detail on request: load the map for the regions behind these figures. */
  onDetail: (code: string) => void;
}

/**
 * Pre-aggregated card shown before any shape is drawn. The heading and the coverage note come from the
 * model, which only calls figures a total when coverage is complete.
 */
export function renderProvinceCard(root: HTMLElement, model: ProvinceCardModel, h: ProvinceCardHandlers): void {
  const wrap = el('div', undefined, 'province');
  wrap.append(el('h2', model.heading));
  wrap.append(el('p', 'Summary from pre-computed regional totals. No map data is loaded for this view.', 'sub'));

  if (h.options.length > 1) {
    const label = el('label', 'Province ', 'province-pick');
    const sel = el('select');
    for (const o of h.options) sel.append(new Option(o.name, o.code));
    sel.value = model.code;
    sel.addEventListener('change', () => h.onProvince(sel.value));
    label.append(sel);
    wrap.append(label);
  }

  const note = el('p', model.coverageText, `note ${model.provincial ? 'info' : 'warn'}`);
  note.setAttribute('role', 'status');
  wrap.append(note);

  for (const iv of model.intervals) {
    const sec = el('section', undefined, 'prov-interval');
    sec.append(el('h3', `${iv.from} to ${iv.to}`));
    sec.append(el('p', `Natural cover in ${iv.from}: ${fmtHa(iv.naturalHa)} ha`, 'sub'));
    const table = el('table');
    table.createCaption().textContent = `Natural habitat converted between ${iv.from} and ${iv.to}, by target`;
    table.caption!.className = 'sr-only';
    const head = table.createTHead().insertRow();
    for (const t of ['Converted to', 'Hectares', 'Percent of natural']) {
      const th = el('th', t);
      th.scope = 'col';
      head.append(th);
    }
    const body = table.createTBody();
    for (const r of iv.rows) {
      const tr = body.insertRow();
      const th = el('th', targetShort(r.target));
      th.scope = 'row';
      tr.append(th, el('td', fmtHa(r.convertedHa)), el('td', fmtPct(r.percent)));
    }
    sec.append(table);
    wrap.append(sec);
  }

  if (model.regionsRun.length > 0) {
    wrap.append(el('p', 'Choose a region above, or draw a shape on the map, for area-specific results.', 'sub'));
    const b = el('button', 'Show map detail for these regions', 'linkbtn');
    b.type = 'button';
    b.addEventListener('click', () => h.onDetail(model.code));
    wrap.append(b);
  }
  root.replaceChildren(wrap);
}
