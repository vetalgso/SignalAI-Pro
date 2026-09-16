import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import ts from 'typescript';

// Use the project's TypeScript compiler; no browser or extra test dependency.
const source = await readFile(new URL('../src/features/signals/qualityReportApi.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext },
});
const { fetchQualityReport } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

const query = { days: 30, source: 'AI_REVIEW', transition_origin: 'AUTOMATIC', offset: 0 };
const report = {
  generated_from: '2026-08-16T00:00:00Z', as_of: '2026-09-15T00:00:00Z',
  source: 'AI_REVIEW', transition_origin: 'AUTOMATIC', offset: 0, limit: 25,
  summary: { total: 1 }, groups: [], total_groups: 0,
};
function respond(t, body, status = 200) {
  return t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(body), { status }));
}
function load(request = query) {
  return fetchQualityReport(request, new AbortController().signal);
}

test('rejects a legacy backend response that silently ignored the origin filter', async t => {
  const { transition_origin, ...legacy } = report;
  respond(t, legacy);
  await assert.rejects(load(), /requested filters/);
});

test('rejects ALL totals returned for Automatic only', async t => {
  respond(t, { ...report, transition_origin: 'ALL' });
  await assert.rejects(load(), /requested filters/);
});

for (const origin of ['ALL', 'AUTOMATIC', 'MANUAL', 'UNKNOWN']) {
  test(`accepts a matching ${origin} response and sends its query`, async t => {
    const expected = { ...report, transition_origin: origin };
    const fetchMock = respond(t, expected);
    const controller = new AbortController();
    assert.deepEqual(await fetchQualityReport({ ...query, transition_origin: origin }, controller.signal), expected);
    const [url, options] = fetchMock.mock.calls[0].arguments;
    const params = new URL(url, 'https://example.test').searchParams;
    assert.equal(params.get('transition_origin'), origin);
    assert.equal(params.get('days'), '30');
    assert.equal(params.get('source'), 'AI_REVIEW');
    assert.equal(params.get('limit'), '25');
    assert.equal(params.get('offset'), '0');
    assert.equal(options.signal, controller.signal);
    assert.equal(options.cache, 'no-store');
  });
}

for (const mismatch of [{ source: 'SCANNER' }, { offset: 25 }, { limit: 100 }]) {
  test(`rejects another cohort or page: ${JSON.stringify(mismatch)}`, async t => {
    respond(t, { ...report, ...mismatch });
    await assert.rejects(load(), /requested filters/);
  });
}

test('accepts a matching empty result rather than treating it as a failure', async t => {
  const empty = { ...report, summary: { total: 0 } };
  respond(t, empty);
  assert.deepEqual(await load(), empty);
});

test('rejects an HTTP error even when its JSON resembles a report', async t => {
  respond(t, report, 503);
  await assert.rejects(load(), /Request failed/);
});

test('a later matching response can recover after a mismatch', async t => {
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(
    calls++ === 0 ? { ...report, transition_origin: 'ALL' } : report,
  )));
  await assert.rejects(load());
  assert.deepEqual(await load(), report);
});

test('passes cancellation through to the caller', async t => {
  const error = new DOMException('Aborted', 'AbortError');
  t.mock.method(globalThis, 'fetch', async () => { throw error; });
  await assert.rejects(load(), e => e === error);
});
