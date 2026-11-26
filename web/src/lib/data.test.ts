import { describe, expect, it } from 'vitest';
import { readJson } from './data';

const res = (body: string, status = 200) => new Response(body, { status });

describe('readJson', () => {
  it('parses valid JSON', async () => {
    expect(await readJson<{ a: number }>(res('{"a":1}'), 'x/meta.json')).toEqual({ a: 1 });
  });
  it('names the file and says not found on 404', async () => {
    await expect(readJson(res('', 404), 'x/meta.json')).rejects.toThrow(/x\/meta\.json.*404.*not found/);
  });
  it('explains an HTML fallback page', async () => {
    await expect(readJson(res('<!doctype html><html>'), 'x/index.json')).rejects.toThrow(/x\/index\.json.*web page.*missing/);
  });
  it('reports invalid JSON by file', async () => {
    await expect(readJson(res('{oops'), 'x/cells.json')).rejects.toThrow(/x\/cells\.json.*not valid JSON/);
  });
});
