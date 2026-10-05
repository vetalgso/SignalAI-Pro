import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

const source = await readFile(new URL('../src/features/signals/RiskDetails.tsx', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
});
const exports = {};
new Function('require', 'exports', outputText)(createRequire(import.meta.url), exports);
const render = (risk, language = 'ru') => renderToStaticMarkup(
  React.createElement(exports.RiskDetails, { risk, language }),
);
const risk = {
  version: 1, calculated_at: '2026-09-22T12:00:00Z', level: 'high', profile_risk: 'medium',
  reason: 'FORECAST_HIGH', horizons: [{ horizon_minutes: 2880, level: 'high' }],
  signal_available: true, warning_count: 0, volume_state: 'AVAILABLE', volume_ratio: 1.3187,
};

test('risk explanation shows the saved first rule and forecast facts', () => {
  const html = render(risk);
  assert.match(html, /Хотя бы один прогнозный горизонт имеет высокий риск/);
  assert.match(html, /2880 мин: Высокий/);
  assert.match(html, /Предупреждений технического сигнала: 0/);
  assert.match(html, /1.3187/);
  assert.match(html, /Первое сработавшее правило/);
});
test('legacy high risk does not invent a cause', () => {
  assert.match(render(null), /Причина высокого риска не записана/);
  assert.doesNotMatch(render(null), /прогнозный горизонт|0,25/);
});
test('English distinguishes profile fallback from technical warnings', () => {
  assert.match(render({ ...risk, reason: 'PROFILE', profile_risk: 'high' }, 'en'), /scan profile risk level was used/);
  assert.match(render({ ...risk, reason: 'SIGNAL_WARNINGS', warning_count: 2 }, 'en'), /at least two warnings/);
});
