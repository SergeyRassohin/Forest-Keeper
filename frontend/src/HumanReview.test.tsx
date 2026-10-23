import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { HumanReview } from './HumanReview';
import type { ReviewContext, Decision } from './decisionTypes';
const decision: Decision = { id: 'decision-1', conflict_id: 'case', entity_id: 'entity', business_key: 'MAT-1', attribute_code: 'mass', domain: 'materials', decision_type: 'SELECT_VALUE', status: 'ACTIVE', selected_value: '12.5', unit: 'kg', selected_source_id: 'source-a', reason: 'Проверен документ', user_id: 'actor', actor_display_name: 'Рецензент', actor_roles: ['REVIEWER'], decided_at: '2026-10-23T00:00:00Z', supersedes_decision_id: null, superseded_by: null, context_snapshot: { evidence: 'historical' } };
const review: ReviewContext = { conflict_id: 'case', conflict_status: 'IN_REVIEW', context_version: 'version-1', review_version: 1, evidence_hash: 'hash', allowed_actions: ['SELECT_VALUE', 'ENTER_VALUE', 'INSUFFICIENT_DATA', 'DEFERRED'], can_start_review: true, can_supersede: false, current_decision: null, history_count: 0, correction_policy: { allowed: true, kind: 'quantity', unit: 'kg', max_length: 4096 }, selectable_values: [{ side: 'A', source_id: 'source-a', source_name: 'CSV', value_id: 'value-a', value: '12.5', unit: 'kg' }], known_unknowns: [] };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: vi.fn(function(this: HTMLDialogElement) { this.open = true; }) });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: vi.fn(function(this: HTMLDialogElement) { this.open = false; }) });
});
function setup(options: { failure?: number; network?: boolean; readOnly?: boolean; history?: boolean } = {}) {
  let attempts = 0;
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (path, init) => {
    const url = String(path);
    if (url.endsWith('/decisions') && init?.method === 'POST') {
      attempts++;
      if (attempts === 1 && options.network) throw new TypeError('network lost');
      if (attempts === 1 && options.failure) return new Response(JSON.stringify({ error: { code: 'REJECTED', message: 'Контекст изменился' } }), { status: options.failure });
      return new Response(JSON.stringify({ decision_id: decision.id, decision, conflict_status: 'RESOLVED', message: 'Исходные системы не изменялись.' }));
    }
    if (url.includes('/decisions?')) return new Response(JSON.stringify(options.history ? Array.from({ length: 50 }, (_, i) => ({ ...decision, id: 'history-' + i })) : []));
    return new Response(JSON.stringify({ ...review, history_count: options.history ? 51 : 0, can_start_review: !options.readOnly, allowed_actions: options.readOnly ? [] : review.allowed_actions }));
  });
}
const expired = vi.fn(); const saved = vi.fn();
async function fill() {
  fireEvent.click(await screen.findByRole('button', { name: 'Начать рассмотрение' }));
  fireEvent.click(await screen.findByLabelText('Источник A: CSV · 12.5 kg'));
  fireEvent.change(screen.getByLabelText('Обоснование решения'), { target: { value: 'Проверен документ' } });
  fireEvent.click(screen.getByRole('button', { name: 'Проверить перед сохранением' }));
  return screen.getByRole('dialog');
}
it('confirms outcome and reason before POST, then displays an actual server receipt with actor and value', async () => {
  const mock = setup(); render(<HumanReview conflictId="case" onSessionExpired={expired} onSaved={saved} />);
  const dialog = await fill();
  expect(dialog).toHaveTextContent('12.5'); expect(dialog).toHaveTextContent('Проверен документ');
  expect(screen.queryByText('Решение сохранено')).not.toBeInTheDocument();
  expect(mock.mock.calls.filter(([, init]) => init?.method === 'POST' && String(init.body).includes('idempotency_key'))).toHaveLength(0);
  expect(within(dialog).getByRole('button', { name: 'Сохранить решение' })).toHaveFocus();
  fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить решение' }));
  expect(await screen.findByText('Решение сохранено')).toBeVisible();
  expect(screen.getByRole('article', { name: 'Карточка решения' })).toHaveTextContent('Рецензент');
  expect(screen.getByRole('article', { name: 'Карточка решения' })).toHaveTextContent('12.5');
});
it('retries the identical payload and key after an unknown response without showing premature success', async () => {
  const mock = setup({ network: true }); render(<HumanReview conflictId="case" onSessionExpired={expired} onSaved={saved} />);
  const dialog = await fill(); fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить решение' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Повторить сохранение' }));
  await screen.findByText('Решение сохранено');
  const requests = mock.mock.calls.filter(([, init]) => init?.method === 'POST' && String(init.body).includes('idempotency_key'));
  expect(requests).toHaveLength(2); expect(requests[0][1]?.body).toEqual(requests[1][1]?.body);
});
it('a stale response removes the draft and requires a fresh explicit review', async () => {
  setup({ failure: 409 }); render(<HumanReview conflictId="case" onSessionExpired={expired} onSaved={saved} />);
  const dialog = await fill(); fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить решение' }));
  await screen.findByRole('alert'); await screen.findByRole('button', { name: 'Начать рассмотрение' });
  expect(screen.queryByLabelText('Обоснование решения')).not.toBeInTheDocument();
  expect(screen.queryByText('Решение сохранено')).not.toBeInTheDocument();
});
it('validation rejection retains the draft for correction', async () => {
  setup({ failure: 422 }); render(<HumanReview conflictId="case" onSessionExpired={expired} onSaved={saved} />);
  const dialog = await fill(); fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить решение' }));
  await screen.findByRole('alert'); expect(screen.getByLabelText('Обоснование решения')).toHaveValue('Проверен документ');
  expect(screen.queryByRole('button', { name: 'Повторить сохранение' })).not.toBeInTheDocument();
});
it('read-only context never exposes a review form or write action', async () => {
  setup({ readOnly: true }); render(<HumanReview conflictId="case" onSessionExpired={expired} onSaved={saved} />);
  await screen.findByText(/Режим просмотра/); expect(screen.queryByRole('button', { name: 'Начать рассмотрение' })).not.toBeInTheDocument();
  expect(screen.queryByRole('radio')).not.toBeInTheDocument();
});
it('history pagination never refreshes a draft evidence token', async () => {
  const mock = setup({ history: true }); render(<HumanReview conflictId="case" onSessionExpired={expired} onSaved={saved} />);
  await fill(); fireEvent.click(screen.getByRole('button', { name: 'Вернуться к проверке' }));
  const readsBefore = mock.mock.calls.filter(([path]) => String(path).endsWith('/review-context')).length;
  fireEvent.click(screen.getByRole('button', { name: 'Следующая история рассмотрения' }));
  await vi.waitFor(() => expect(mock).toHaveBeenCalledWith(expect.stringContaining('offset=50'), expect.anything()));
  expect(mock.mock.calls.filter(([path]) => String(path).endsWith('/review-context'))).toHaveLength(readsBefore);
  expect(screen.getByLabelText('Обоснование решения')).toHaveValue('Проверен документ');
});
