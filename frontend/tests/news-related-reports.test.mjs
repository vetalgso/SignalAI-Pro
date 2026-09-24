import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

const source = await readFile(new URL('../src/features/news/RelatedReports.tsx', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
});
const exports = {};
new Function('require', 'exports', outputText)(createRequire(import.meta.url), exports);
const render = (coverage, language = 'ru') => renderToStaticMarkup(
  React.createElement(exports.RelatedReports, { coverage, language }),
);
const report = {
  source: 'CoinDesk', title: 'Bitcoin ETFs attracted $1 billion', url: 'https://coindesk.com/story',
  published_at: '2026-09-22T12:00:00Z',
  basis: { family: 'ETF_FLOW', asset: 'BTC', amount: '1000000000', unit: 'USD', direction: 'INFLOW', shared_terms: [] },
};
const coverage = { version: 1, other_publishers_count: 1, reports: [report] };
test('related report displays link and match facts, explicitly not verification', () => {
  const html = render(coverage);
  assert.match(html, /Проверка фактов не выполнена/);
  assert.match(html, /других изданий — 1/);
  assert.match(html, /пересказывать один источник/);
  assert.match(html, /не подтверждение фактов/);
  assert.match(html, /href="https:\/\/coindesk.com\/story"/);
  assert.match(html, /1000000000 USD/);
  assert.match(html, /2026-09-22T12:00:00Z/);
});
test('empty and legacy reports are not labeled false', () => {
  assert.match(render({ ...coverage, reports: [] }), /не означает, что новость ложная/);
  assert.match(render(null), /ещё не записано/);
  assert.doesNotMatch(render({ ...coverage, version: 2 }), /href=/);
});
test('publisher counts are distinct and computed from displayed links', () => {
  assert.match(render({ ...coverage, other_publishers_count: 99,
    reports: [report, { ...report, url: 'https://coindesk.com/another' }] }), /других изданий — 1/);
});
test('unsafe or misattributed links are not rendered', () => {
  for (const url of ['javascript:alert(1)', 'https://coindesk.com.evil.test/story',
    'https://evil.test/story', 'https://user:pass@coindesk.com/story']) {
    assert.doesNotMatch(render({ ...coverage, reports: [{ ...report, url }] }), /href=/);
  }
});
test('English and recovery match show limitations and shared entity', () => {
  const html = render({ ...coverage, reports: [{ ...report,
    basis: { family: 'ASSET_RECOVERY', asset: 'BTC', amount: '52', unit: 'BTC', direction: 'RECOVERY', shared_terms: ['coldcard'] },
  }] }, 'en');
  assert.match(html, /does not verify the claims/);
  assert.match(html, /52 BTC/);
  assert.match(html, /coldcard/);
});
