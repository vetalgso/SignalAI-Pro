import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/features/signals/aiAdmissionApi.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext },
});
const { fetchAdmission } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const page = {
  run: { id: 393, completed_at: '2026-09-19T06:20:00Z', scanned_assets: 30 },
  items: [{ candidate_id: 1, symbol: 'BTCUSDT', decision: null }],
  total: 1, limit: 25, offset: 0, reason_counts: {}, not_recorded_count: 1,
};
const load = (runId = null, offset = 0) => fetchAdmission(runId, offset, new AbortController().signal);

test('requests latest scan without caching or recomputing legacy decisions', async t => {
  const mock = t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(page)));
  assert.deepEqual(await load(), page);
  const [url, options] = mock.mock.calls[0].arguments;
  assert.equal(new URL(url, 'https://example.test').searchParams.has('run_id'), false);
  assert.equal(options.cache, 'no-store');
});

test('keeps pagination pinned to the displayed scan', async t => {
  const expected = { ...page, offset: 25, items: [] };
  const mock = t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(expected)));
  assert.deepEqual(await load(393, 25), expected);
  const params = new URL(mock.mock.calls[0].arguments[0], 'https://example.test').searchParams;
  assert.equal(params.get('run_id'), '393');
  assert.equal(params.get('offset'), '25');
});

for (const changed of [{ run: { ...page.run, id: 394 } }, { offset: 25 }, { limit: 100 }]) {
  test(`rejects mismatched scan/page ${JSON.stringify(changed)}`, async t => {
    t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ ...page, ...changed })));
    await assert.rejects(load(393), /requested scan/);
  });
}

test('accepts an empty journal, but does not treat an HTTP error as empty', async t => {
  const empty = { ...page, run: null, items: [], total: 0, not_recorded_count: 0 };
  let status = 200;
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(empty), { status }));
  assert.deepEqual(await load(), empty);
  status = 404;
  await assert.rejects(load(), /request failed/);
});

test('passes abort signal through and propagates cancellation', async t => {
  const controller = new AbortController();
  const abort = new DOMException('Aborted', 'AbortError');
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    assert.equal(options.signal, controller.signal);
    throw abort;
  });
  await assert.rejects(fetchAdmission(null, 0, controller.signal), e => e === abort);
});
