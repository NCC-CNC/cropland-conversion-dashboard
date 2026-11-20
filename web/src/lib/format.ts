export function fmtHa(v: number): string {
  return v.toLocaleString('en-CA', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

export function fmtPct(v: number | null): string {
  return v === null ? 'n/a' : `${v.toFixed(1)}%`;
}

export function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
