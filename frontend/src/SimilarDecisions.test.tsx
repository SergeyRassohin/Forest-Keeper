import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { SimilarDecisions } from './SimilarDecisions';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const expired = vi.fn();
it.each([
  ['UNAVAILABLE', 'PROVIDER_UNAVAILABLE', 'Поиск временно недоступен. История решений и рассмотрение конфликта доступны.'],
  ['INDEXING', 'INDEX_NOT_READY', 'Индекс ещё строится. Повторите поиск позже.'],
  ['NO_PRECEDENT', 'NO_HISTORY', 'Похожих подтверждённых решений пока нет.'],
  ['NO_PRECEDENT', 'NO_ACCESSIBLE_PRECEDENT', 'Нет доступных решений в вашей области данных.'],
])('distinguishes %s / %s', async (state, reason_code, text) => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ state, reason_code, results: [] })));
  render(<SimilarDecisions conflictId="case" onSessionExpired={expired} />);
  expect(await screen.findByText(text)).toBeVisible();
  expect(screen.getByText('Похожие решения показывают прошлый опыт. Они не являются автоматическим решением текущего конфликта.')).toBeVisible();
});
it('shows actual history and opens its ID without prefilling a new decision', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ state: 'READY', embedding_model: { is_test: true }, results: [{ decision_id: 'past-id', conflict_id: 'past-case', similarity: .912345, matched_features: ['domain', 'unit'], mismatched_features: ['observations'], actor: { display_name: 'Эксперт' }, decided_at: '2026-10-23T00:00:00Z', outcome: 'SELECT_VALUE', selected_value: '12.5', unit: 'kg', reason: 'Проверен документ' }] })));
  const open = vi.fn();
  render(<SimilarDecisions conflictId="case" onSessionExpired={expired} onOpenDecision={open} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Открыть прошлое решение' }));
  expect(open).toHaveBeenCalledWith('past-id');
  expect(screen.getByText('Похожесть 91.23%')).toBeVisible();
  expect(screen.getByText('Проверен документ')).toBeVisible();
  expect(screen.getByText(/Совпало: Область данных, Единица измерения/)).toBeVisible();
  expect(fetch.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
});
it('can retry errors and does not reuse a previous case response', async () => {
  vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new TypeError('network')).mockResolvedValue(new Response(JSON.stringify({ state: 'NO_PRECEDENT', reason_code: 'NO_HISTORY', results: [] })));
  render(<SimilarDecisions conflictId="case" onSessionExpired={expired} />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить');
  fireEvent.click(screen.getByRole('button', { name: 'Повторить поиск' }));
  expect(await screen.findByText('Похожих подтверждённых решений пока нет.')).toBeVisible();
});
