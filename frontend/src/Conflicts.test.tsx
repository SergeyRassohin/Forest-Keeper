import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Conflicts } from './Conflicts';
const row = { id: 'conflict-1', entity_id: 'entity', matching_run_id: 'match', attribute_code: 'mass', conflict_type: 'VALUE_MISMATCH', severity: 'LOW', status: 'OPEN', detected_at: '2026-10-21T12:00:00Z' };
const detail = { ...row, based_on_previous_profile: false, match_candidate_id: 'candidate', normalization_origins: ['A', 'B'].map((source_id) => ({ analysis_id: 'norm-' + source_id, source_id, profile_id: 'profile-' + source_id, profile_version: '1', mapping_hash: 'hash-' + source_id, engine_version: 'fk-normalization/1' })), basis: { reason_code: 'NORMALIZED_VALUES_DIFFER', engine_version: 'fk-conflicts/1', config_hash: 'config', matching_profile_hash: 'matching', matching_evidence: {} }, values_snapshot: ['A', 'B'].map((source_name, index) => ({ source_name, source_id: source_name, source_record_key: 'DIFF', raw_record_id: source_name, entity_id: 'entity', filename: source_name + '.csv', file_hash: 'sha256', source_position: { row: 2 }, presence: 'PRESENT', value: { raw_value: index ? '12.4 kg' : '<script>alert(1)</script>', normalized_value: index ? '12.4' : '12.5', unit: 'kg', quality_status: 'VALID', normalization_rule: { code: 'OK' } } })) };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function setup(historical = false) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (path, init) => {
    const url = String(path);
    const body = init?.method === 'POST' ? { id: 'run' } : url.includes('/conflicts/conflict-1') ? { ...detail, based_on_previous_profile: historical } : url.includes('/conflicts?') ? [row] : url.includes('/matching-runs') ? [{ id: 'match', status: 'COMPLETED' }] : [];
    return new Response(JSON.stringify(body), { status: 200 });
  });
}
const user = (permissions: string[]) => ({ id: 'user', login: 'viewer', display_name: 'Viewer', roles: ['VIEWER'], permissions });
it('shows raw normalized values provenance and honest human boundary, escaping hostile values', async () => {
  setup(); render(<Conflicts user={user(['conflict.view'])} onSessionExpired={() => {}} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Открыть конфликт ' + row.id }));
  expect(await screen.findByText('Нормализованные значения одного атрибута различаются.')).toBeVisible();
  expect(screen.getByText('<script>alert(1)</script>')).toBeVisible();
  expect(document.querySelector('script')).toBeNull();
  expect(screen.getByRole('region', { name: 'Источники нормализации' })).toHaveTextContent('norm-A');
  expect(screen.getByRole('region', { name: 'Источники нормализации' })).toHaveTextContent('norm-B');
  expect(screen.getByRole('region', { name: 'Источники нормализации' })).toHaveTextContent('Профиль: profile-B v1');
  expect(screen.getByText('Решение сохраняется отдельно от найденного расхождения. Исходные системы не изменяются.')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Проверить конфликты' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Выбрать значение|Исправить|Принять рекомендацию/ })).not.toBeInTheDocument();
});
it('runs authorized analysis and filters by matching input', async () => {
  const mock = setup(); render(<Conflicts user={user(['conflict.view','analysis.run'])} onSessionExpired={() => {}} initialRunId="match" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Проверить конфликты' }));
  await vi.waitFor(() => expect(mock).toHaveBeenCalledWith('/api/v1/conflict-runs', expect.objectContaining({ method: 'POST', body: '{"matching_run_id":"match"}' })));
  fireEvent.change(screen.getByLabelText('Тип конфликта'), { target: { value: 'MISSING' } });
  await vi.waitFor(() => expect(mock).toHaveBeenCalledWith(expect.stringContaining('conflict_type=MISSING'), expect.anything()));
});
it('marks results from a previous profile explicitly', async () => {
  setup(true); render(<Conflicts user={user(['conflict.view'])} onSessionExpired={() => {}} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Открыть конфликт ' + row.id }));
  expect(await screen.findByText(/Результат по предыдущей версии профиля/)).toBeVisible();
});
it('expires the session on unauthorized API response', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401 }));
  const expired = vi.fn(); render(<Conflicts user={user(['conflict.view'])} onSessionExpired={expired} />);
  await vi.waitFor(() => expect(expired).toHaveBeenCalled());
});
it('clears a selected detail when the list filter changes', async () => {
  setup(); render(<Conflicts user={user(['conflict.view'])} onSessionExpired={() => {}} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Открыть конфликт ' + row.id }));
  await screen.findByRole('region', { name: 'Карточка конфликта' });
  fireEvent.change(screen.getByLabelText('Тип конфликта'), { target: { value: 'RULE_VIOLATION' } });
  expect(screen.queryByRole('region', { name: 'Карточка конфликта' })).not.toBeInTheDocument();
});
it('does not describe an omitted long raw value as absent', async () => {
  const omitted = { ...detail, values_snapshot: detail.values_snapshot.map((item, index) => index ? item : { ...item, value: { ...item.value, raw_value: null, raw_value_omitted: true } }) };
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (path) => new Response(JSON.stringify(String(path).includes('/conflicts/conflict-1') ? omitted : String(path).includes('/conflicts?') ? [row] : []), { status: 200 }));
  render(<Conflicts user={user(['conflict.view'])} onSessionExpired={() => {}} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Открыть конфликт ' + row.id }));
  expect(await screen.findByText('Сохранено в оригинале')).toBeVisible();
  expect(screen.queryByText('Не задано')).not.toBeInTheDocument();
});
