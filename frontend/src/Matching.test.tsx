import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Matching } from './Matching';
import type { User } from './api';
const profile = { id: 'profile', code: 'synthetic-material', version: '1', synthetic: true };
const run = { id: 'run', status: 'COMPLETED', records_processed: 2, candidates_generated: 1, status_counts: { POSSIBLE_MATCH: 1 }, diagnostics: {}, profile_hash: 'hash', profile_snapshot: { code: 'synthetic-material', version: '1', engine_version: 'fk-matching/1' }, based_on_previous_profile: false };
const candidate = { id: 'pair', run_id: 'run', status: 'POSSIBLE_MATCH', confidence: '0.900000', reason: 'NO_APPROVED_FUZZY_THRESHOLD', raw_record_a_id: 'raw-a', raw_record_b_id: 'raw-b', confirmed_by: null };
const user = (permissions: string[]): User => ({ id: 'user', login: 'expert', display_name: 'Expert', roles: [], permissions });
const detail = () => ({ ...candidate, run, evidence: { signals: [{ attribute_code: 'name', algorithm: 'token_sort_ratio', inputs: ['БОЛТ М8', 'БОЛТ МВ'], score: '0.9', weight: '1', weighted_contribution: '.9', tolerance: '0', code: 'COMPARED' }], threshold_policy: 'EXACT_RULES_ONLY_NO_FUZZY_AUTO', threshold_decision: 'OPEN', blocking: ['name_prefix'], input_context: { gold_reference_version: null } }, records: ['CSV', '1C'].map((name,index) => ({ raw_record_id: 'raw-' + index, source: { name, code: name }, filename: 'input.csv', file_hash: 'checksum', source_record_key: '001', source_position: { row: 2 }, values: [{ attribute_code: 'mass', raw_value: index ? '12500 г' : '12,5 кг', normalized_value: '12.5', unit: 'kg', quality_status: 'VALID' }] })) });
function setup(historical = false) {
  let reviewed = false;
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (request, init) => {
    const path = String(request); let body: unknown;
    if (init?.method === 'POST') { reviewed = true; body = { ...candidate, status: 'MATCHED' }; }
    else if (path.includes('/matching-profiles')) body = [profile];
    else if (path.includes('/analysis?')) body = [];
    else if (path.includes('/match-candidates/')) body = { ...detail(), ...(reviewed ? { status: 'MATCHED', confirmed_by: 'reviewer', manual_review: { actor_id: 'reviewer', reviewed_at: '2026-10-20T17:00:00Z', reason: 'Документы проверены', from_status: 'POSSIBLE_MATCH', to_status: 'MATCHED' } } : {}) };
    else if (path.includes('/candidates?')) body = [candidate];
    else if (path.endsWith('/matching-runs/run')) body = { ...run, based_on_previous_profile: historical, diagnostics: { coverage_limited: historical } };
    else body = [run];
    return new Response(JSON.stringify(body), { status: 200 });
  });
}
async function open() {
  await waitFor(() => expect(screen.getByRole('combobox', { name: 'Запуск сопоставления' }).querySelectorAll('option')).toHaveLength(2));
  fireEvent.change(screen.getByRole('combobox', { name: 'Запуск сопоставления' }), { target: { value: 'run' } });
  fireEvent.click(await screen.findByRole('button', { name: 'Сравнить записи raw-a ↔ raw-b' }));
  await screen.findByRole('region', { name: 'Основание сопоставления' });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
describe('Matching browser screen', () => {
  it('shows original values, normalized units and signals without viewer mutations', async () => {
    setup(); render(<Matching user={user(['match.view'])} onSessionExpired={vi.fn()} />); await open();
    expect(screen.getByText('12,5 кг')).toBeInTheDocument(); expect(screen.getByText('12500 г')).toBeInTheDocument();
    expect(screen.getAllByText('12.5')).toHaveLength(2); expect(screen.getByText('name / token_sort_ratio')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Запустить сопоставление' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Подтвердить совпадение' })).not.toBeInTheDocument();
  });
  it('requires a reason and sends explicit manual review', async () => {
    const fetch = setup(); render(<Matching user={user(['match.view', 'match.review'])} onSessionExpired={vi.fn()} />); await open();
    const button = screen.getByRole('button', { name: 'Подтвердить совпадение' }); expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Причина подтверждения или отклонения'), { target: { value: 'Документы проверены' } }); fireEvent.click(button);
    await waitFor(() => expect(fetch.mock.calls.some(([path, init]) => String(path).endsWith('/pair/review') && init?.body === JSON.stringify({ status: 'MATCHED', reason: 'Документы проверены' }))).toBe(true));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Подтвердить совпадение' })).not.toBeInTheDocument());
    expect(screen.getByRole('region', { name: 'Решение человека' })).toHaveTextContent('Документы проверены');
  });
  it('warns about old criteria and incomplete coverage', async () => {
    setup(true); render(<Matching user={user(['match.view'])} onSessionExpired={vi.fn()} />); await open();
    expect(screen.getByText(/Результат рассчитан по предыдущей версии/)).toBeInTheDocument(); expect(screen.getByText(/Пропущенные пары не объявлены/)).toBeInTheDocument();
  });
  it('expires sessions after a 401 response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401 }));
    const expired = vi.fn(); render(<Matching user={user(['match.view'])} onSessionExpired={expired} />); await waitFor(() => expect(expired).toHaveBeenCalled());
  });
});
