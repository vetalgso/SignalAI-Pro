import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

// Render the real pure component using the existing TypeScript/React packages.
const source = await readFile(new URL('../src/features/signals/QualityPenaltyDetails.tsx', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
});
const exports = {};
new Function('require', 'exports', outputText)(createRequire(import.meta.url), exports);
const render = (quality, maximum = 20, language = 'ru') => renderToStaticMarkup(
  React.createElement(exports.QualityPenaltyDetails, { quality, maximum, language }),
);
const quality = {
  version: 1, calculated_at: '2026-09-21T08:03:39Z',
  forecast: { points: 15, state: 'AVAILABLE', uncertain_count: 4,
    horizons: [60, 240, 1440, 2880].map(horizon_minutes => ({ horizon_minutes, direction: 'UNCERTAIN' })) },
  volume: { points: 15, state: 'AVAILABLE', ratio: 0.2 },
  news: { points: 10, state: 'AVAILABLE', article_count: 10, unverified_count: 9 },
  uncapped_total: 40, cap: 30, total: 30,
};

test('shows component sum, capped total and stored AI maximum as distinct numbers', () => {
  const html = render(quality);
  assert.match(html, /30 балл\./);
  assert.match(html, /Максимум для AI: 20/);
  assert.match(html, /Сумма категорий: 40/);
  assert.match(html, /ограничение суммы: 30/);
  assert.match(html, /Прогнозы: 15 балл\./);
  assert.match(html, /Новости: 10 балл\./);
});

test('shows original uncertainty and the 2-day horizon without replacing them with LONG', () => {
  const html = render(quality);
  assert.match(html, /2 дн\.: Неопределённый \(UNCERTAIN\)/);
  assert.match(html, /Неопределённых или боковых: 4 \/ 4/);
  assert.match(html, /LONG\/SHORT.*рассчитываются отдельно/);
});

test('legacy data is explicitly missing, including an absent saved maximum', () => {
  const html = render(null, null);
  assert.match(html, /Состав штрафа не записан/);
  assert.match(html, /Максимум для AI: Не записан/);
  assert.doesNotMatch(html, /20|30|балл\./);
});

test('missing volume and news do not claim low volume or unverified articles', () => {
  const html = render({ ...quality,
    volume: { points: 10, state: 'MISSING', ratio: null },
    news: { points: 5, state: 'MISSING', article_count: 0, unverified_count: 0 },
  });
  assert.match(html, /Отношение объёма к среднему отсутствует/);
  assert.match(html, /Данные отсутствуют или список пуст/);
  assert.doesNotMatch(html, /Без статуса verified:/);
});

test('English text distinguishes invalid volume from zero and preserves zero maximum', () => {
  const html = render({ ...quality, volume: { points: 10, state: 'INVALID', ratio: null } }, 0, 'en');
  assert.match(html, /Invalid volume ratio/);
  assert.match(html, /AI maximum: 0/);
  assert.match(html, /2 d: Uncertain/);
  assert.match(render({ ...quality, volume: { points: 15, state: 'AVAILABLE', ratio: 0 } }, 20, 'en'), /Volume \/ average: 0/);
});
