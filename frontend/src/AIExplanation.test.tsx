import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AIExplanation } from './AIExplanation';
import { ThemeSwitch } from './ThemeSwitch';

const conflict = '11111111-1111-4111-8111-111111111111';
const handle = '22222222-2222-5222-8222-222222222222';
const decision = '33333333-3333-4333-8333-333333333333';
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
function ready() {
  return { request_id: handle, state: 'COMPLETED', context_fingerprint: 'a'.repeat(64),
    clauses: [{ code: 'CURRENT_CONTEXT', text: 'Сравниваются 12.5 kg и 12.4 kg.', decision_ids: [] },
      { code: 'SUPPORT', text: 'Проверенный пример прошлой практики.', decision_ids: [decision] },
      { code: 'LIMITATION', text: 'Решение принимает человек.', decision_ids: [] }],
    model: { model_id: 'Qwen/Qwen3-8B-GGUF', revision: 'b'.repeat(40), prompt_version: 'grounded-clauses-v4',
      quality_provenance: 'LOCAL_QWEN_DEMO', production_accepted: false } };
}
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); delete document.documentElement.dataset.theme; });

it('makes no automatic AI request and an explicit request displays verified evidence links', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, options) =>
    response(options?.method === 'POST' ? { request_id: handle } : ready()));
  const open = vi.fn();
  render(<AIExplanation conflictId={conflict} contextVersion="current" onSessionExpired={vi.fn()} onOpenDecision={open} />);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Получить AI-объяснение' }));
  expect(await screen.findByText('Сравниваются 12.5 kg и 12.4 kg.')).toBeInTheDocument();
  expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: 'Посмотреть подтверждённое решение' }));
  expect(open).toHaveBeenCalledWith(decision);
});

it('drops a late response after the current review context changes', async () => {
  let finish: ((value: Response) => void) | undefined;
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, options) =>
    options?.method === 'POST' ? response({ request_id: handle }) : new Promise<Response>(resolve => { finish = resolve; }));
  const props = { conflictId: conflict, onSessionExpired: vi.fn() };
  const view = render(<AIExplanation {...props} contextVersion="before" />);
  fireEvent.click(screen.getByRole('button', { name: 'Получить AI-объяснение' }));
  await waitFor(() => expect(finish).toBeDefined());
  view.rerender(<AIExplanation {...props} contextVersion="after" />);
  await act(async () => { finish!(response(ready())); });
  expect(screen.queryByText('Сравниваются 12.5 kg и 12.4 kg.')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Получить AI-объяснение' })).toBeEnabled();
});

it('preserves a draft and the completed explanation across light/dark changes', async () => {
  vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, options) =>
    response(options?.method === 'POST' ? { request_id: handle } : ready()));
  render(<><ThemeSwitch /><textarea aria-label="Черновик решения" defaultValue="Проверю документ" />
    <AIExplanation conflictId={conflict} contextVersion="same" onSessionExpired={vi.fn()} /></>);
  const draft = screen.getByLabelText('Черновик решения');
  fireEvent.click(screen.getByRole('button', { name: 'Получить AI-объяснение' }));
  await screen.findByText('Сравниваются 12.5 kg и 12.4 kg.');
  fireEvent.click(screen.getByRole('button', { name: 'Тёмная тема' }));
  expect(draft).toHaveValue('Проверю документ');
  expect(screen.getByLabelText('Черновик решения')).toBe(draft);
  expect(screen.getByText('Проверенный пример прошлой практики.')).toBeInTheDocument();
});

it('treats malformed model responses as unavailable without breaking a draft', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, options) =>
    response(options?.method === 'POST' ? { request_id: handle } : { request_id: handle, state: 'COMPLETED' }));
  render(<><textarea aria-label="Черновик решения" defaultValue="Мой выбор" /><AIExplanation conflictId={conflict} contextVersion="current" onSessionExpired={vi.fn()} /></>);
  fireEvent.click(screen.getByRole('button', { name: 'Получить AI-объяснение' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Ручное рассмотрение остаётся доступно');
  expect(screen.getByLabelText('Черновик решения')).toHaveValue('Мой выбор');
});

it('cancels waiting only after server confirmation and never sends a Decision', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    if (String(url).endsWith('/cancel')) return response({ request_id: handle, state: 'FAILED', reason_code: 'AI_CANCELLED' });
    return response(options?.method === 'POST' ? { request_id: handle } : { request_id: handle, state: 'QUEUED' });
  });
  render(<AIExplanation conflictId={conflict} contextVersion="current" onSessionExpired={vi.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Получить AI-объяснение' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Отменить ожидание' }));
  expect(await screen.findByText('Ожидание отменено. Ручное рассмотрение доступно.')).toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => String(url).endsWith('/decisions'))).toBe(false);
});

it('reports an expired cookie session', async () => {
  const expired = vi.fn();
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({}, 401));
  render(<AIExplanation conflictId={conflict} contextVersion="current" onSessionExpired={expired} />);
  fireEvent.click(screen.getByRole('button', { name: 'Получить AI-объяснение' }));
  await waitFor(() => expect(expired).toHaveBeenCalledOnce());
});

it('rejects an unsupported production-quality claim', async () => {
  const value = ready(); value.model.production_accepted = true;
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, options) =>
    response(options?.method === 'POST' ? { request_id: handle } : value));
  render(<AIExplanation conflictId={conflict} contextVersion="current" onSessionExpired={vi.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Получить AI-объяснение' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Ручное рассмотрение остаётся доступно');
  expect(screen.queryByText('Проверенный пример прошлой практики.')).not.toBeInTheDocument();
});
