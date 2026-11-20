import type { AreaEntry } from './types';

function isFixture(a: AreaEntry): boolean {
  return /fixture/i.test(a.id) || /fixture/i.test(a.name);
}

/** Hide synthetic fixture entries as soon as at least one real area exists. */
export function visibleAreas(areas: AreaEntry[]): AreaEntry[] {
  const real = areas.filter((a) => !isFixture(a));
  return real.length > 0 ? real : areas;
}
