import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { Recommendation } from './Recommendation';
import { HumanReview } from './HumanReview';
import { ThemeSwitch } from './ThemeSwitch';
import type { RecommendationResult } from './recommendationTypes';

const recommendation: RecommendationResult = {
  conflict_id: 'case', status: 'RECOMMENDED', recommended_action: 'SELECT_VALUE',
  recommended_source_id: 'source-a', recommended_value_id: 'value-a',
  recommended_value: { kind: 'quantity', value: '12.5', unit: 'kg' },
  confidence: 5, confidence_unit: 'INDEPENDENT_PROVENANCE_GROUPS', confidence_label: 'SUFFICIENT_DEMONSTRATION_EVIDENCE',
  reason_code: 'UNANIMOUS_INDEPENDENT_PRECEDENTS', reasoning_summary: 'Пять согласованных групп прошлых случаев.',
  limitations: ['Только демонстрация'], evidence_summary: { independent_groups: 5, minimum_groups: 5 },
  quality_provenance: 'DEMONSTRATION_ONLY', evidence: [{ decision_id: 'past-real-id', actor_display_name: 'Эксперт',
    decided_at: '2026-10-25T00:00:00Z', outcome: 'SELECT_VALUE', reason: '<img src=x onerror=alert(1)>',
    selected_value: '12.5', unit: 'kg', logical_role: 'REGISTER_EXPORT', context_summary: { subject: 'Болт', attribute_code: 'mass' },
    source_correspondence: [{ historical_source_id: 'old-source', current_source_id: 'source-a', logical_role: 'REGISTER_EXPORT' }] }],
  supporting_decision_ids: ['past-real-id'], conflicting_evidence: [], authority_reference: 'NOT_DEFINED',
  rules_status: 'NOT_CONFIGURED', template_status: 'NOT_CONFIGURED', recommendation_policy_version: 'stage8-demo-unanimous-v1',
  recommendation_policy_hash: 'policy-hash', source_mapping_version: 'explicit-v1', retrieval_version: 'retrieval',
  context_fingerprint: 'fingerprint', review_context_version: 'version-1', generated_at: '2026-10-25T00:00:00Z', audit_reference: 'audit-receipt',
};
const values = [{ side: 'A', source_id: 'source-a', source_name: 'Рабочая выгрузка', value_id: 'value-a', value: '12.5', unit: 'kg' }];
const callbacks = { onUse: vi.fn(), onInvalidated: vi.fn(), onContextChanged: vi.fn(), onOpenDecision: vi.fn(), onSessionExpired: vi.fn() };
const props = { conflictId: 'case', contextVersion: 'version-1', currentValues: values, canUse: true, disabled: false, ...callbacks };
beforeEach(() => { Object.values(callbacks).forEach(fn => fn.mockReset()); });
afterEach(() => { vi.restoreAllMocks(); localStorage.clear(); delete document.documentElement.dataset.theme; delete document.documentElement.dataset.themePreference; });
function json(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status }); }

it('explains evidence strength without probability and only prefills on an explicit click', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(recommendation));
  render(<Recommendation {...props} />);
  expect(await screen.findByText(/5 согласованных независимых групп/)).toBeVisible();
  expect(screen.getByText(/Демонстрационная рекомендация/)).toBeVisible();
  expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeVisible();
  expect(document.querySelector('img')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Посмотреть основание решения' }));
  expect(callbacks.onOpenDecision).toHaveBeenCalledWith('past-real-id');
  fireEvent.click(screen.getByRole('button', { name: 'Использовать предложение в форме' }));
  expect(callbacks.onUse).toHaveBeenCalledWith(recommendation);
  expect(fetch.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
});
it('treats abstention as an ordinary visible outcome without a chosen value', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ ...recommendation, status: 'ABSTAINED', recommended_value: null,
    recommended_value_id: null, recommended_source_id: null, confidence: null, reasoning_summary: 'Противоречивые основания.', conflicting_evidence: ['past-real-id'] }));
  render(<Recommendation {...props} />);
  expect(await screen.findByText('Нет обоснованной рекомендации')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Использовать предложение в форме' })).not.toBeInTheDocument();
  expect(screen.queryByText(/Сила основания/)).not.toBeInTheDocument();
});
it('keeps viewer/admin-only readers out of the form bridge', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(recommendation));
  render(<Recommendation {...props} canUse={false} />);
  expect(await screen.findByRole('button', { name: 'Использовать предложение в форме' })).toBeDisabled();
});
it('removes prior evidence immediately on a revoked-scope refresh', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(json(recommendation)).mockResolvedValueOnce(json({}, 404));
  render(<Recommendation {...props} />);
  await screen.findByText(/past-real-id/);
  fireEvent.click(screen.getByRole('button', { name: 'Обновить рекомендацию' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('области доступа');
  expect(screen.queryByText(/past-real-id/)).not.toBeInTheDocument();
  expect(callbacks.onInvalidated).toHaveBeenCalled();
});
it('expires a session without retaining old recommendation evidence', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({}, 401));
  render(<Recommendation {...props} />);
  await vi.waitFor(() => expect(callbacks.onSessionExpired).toHaveBeenCalled());
});
it('requests a new human context when the server token changes', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ ...recommendation, review_context_version: 'changed' }));
  render(<Recommendation {...props} />);
  await vi.waitFor(() => expect(callbacks.onContextChanged).toHaveBeenCalled());
  expect(screen.queryByText(/past-real-id/)).not.toBeInTheDocument();
});

it('requires human reason/confirmation, preserves draft through theme switch and sends a validated receipt', async () => {
  let version = 'version-0';
  const review = () => ({ conflict_id: 'case', conflict_status: version === 'version-0' ? 'OPEN' : 'IN_REVIEW', context_version: version,
    review_version: 1, evidence_hash: 'hash', allowed_actions: ['SELECT_VALUE', 'DEFERRED'], can_start_review: true, can_supersede: false,
    current_decision: null, history_count: 0, correction_policy: { allowed: false }, selectable_values: values, known_unknowns: [] });
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async (path, init) => {
    const url = String(path);
    if (url.endsWith('/recommendation')) return json({ ...recommendation, review_context_version: version });
    if (url.includes('/decisions?')) return json([]);
    if (url.endsWith('/review') && init?.method === 'POST') { version = 'version-1'; return json(review()); }
    if (url.endsWith('/decisions') && init?.method === 'POST') return json({ decision_id: 'new-real-id', conflict_status: 'RESOLVED', message: 'Сохранено',
      decision: { id: 'new-real-id', business_key: 'Bolt', decision_type: 'SELECT_VALUE', status: 'ACTIVE', selected_value: '12.5', user_id: 'actor', actor_roles: ['REVIEWER'], decided_at: '2026-10-25T00:00:00Z' } });
    return json(review());
  });
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function(this: HTMLDialogElement) { this.open = true; } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function(this: HTMLDialogElement) { this.open = false; } });
  render(<><ThemeSwitch /><HumanReview conflictId="case" showRecommendations canAcceptRecommendation onSaved={vi.fn()} onSessionExpired={callbacks.onSessionExpired} /></>);
  fireEvent.click(await screen.findByRole('button', { name: 'Начать рассмотрение' }));
  await vi.waitFor(() => expect(screen.getByRole('button', { name: 'Использовать предложение в форме' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Использовать предложение в форме' }));
  fireEvent.change(screen.getByLabelText('Обоснование решения'), { target: { value: 'Моё самостоятельное обоснование' } });
  fireEvent.click(screen.getByRole('button', { name: 'Тёмная тема' }));
  expect(screen.getByLabelText('Обоснование решения')).toHaveValue('Моё самостоятельное обоснование');
  expect(screen.getByRole('radio', { name: /Источник A/ })).toBeChecked();
  const posts = () => fetch.mock.calls.filter(([path, init]) => String(path).endsWith('/decisions') && init?.method === 'POST');
  expect(posts()).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: 'Проверить перед сохранением' }));
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Сохранить решение' }));
  await screen.findByText('Решение сохранено');
  expect(JSON.parse(String(posts()[0][1]?.body))).toMatchObject({ recommendation_reference: 'audit-receipt', context_version: 'version-1', confirmed: true, reason: 'Моё самостоятельное обоснование' });
});
