import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Imports } from './Imports';

const viewer = { id: 'v', login: 'v', display_name: 'Viewer', roles: ['VIEWER'], permissions: ['source.view', 'import.view'] };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it('lets a viewer read raw values but does not offer upload or source creation', async () => {
  const batch = { id: 'batch', original_filename: 'original.csv', status: 'COMPLETED', source_name: 'Source', records_loaded: 1, records_failed: 0, file_hash: '123', uploaded_at: '2026-10-19T12:00:00Z' };
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
    if (url.includes('/records')) return Promise.resolve(response([{ id: 'raw', raw_payload: { id: '001', value: '<script>raw</script>' }, source_position: { line_start: 2 } }]));
    if (url.includes('/errors') || url.includes('/sources')) return Promise.resolve(response([]));
    if (url.endsWith('/batch')) return Promise.resolve(response(batch));
    return Promise.resolve(response([batch]));
  }));
  render(<Imports user={viewer} onSessionExpired={vi.fn()} />);
  fireEvent.click(await screen.findByRole('button', { name: 'original.csv' }));
  expect(await screen.findByText(/<script>raw<\/script>/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Загрузить' })).not.toBeInTheDocument();
  expect(screen.queryByText('Добавить источник')).not.toBeInTheDocument();
  expect(document.querySelector('script')).toBeNull();
});

it('returns to sign-in when import permission requests lose the session', async () => {
  const expired = vi.fn();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({}, 401)));
  render(<Imports user={viewer} onSessionExpired={expired} />);
  await vi.waitFor(() => expect(expired).toHaveBeenCalled());
});

function delayedRecords() {
  const aborted = vi.fn();
  const batch = (id: string) => ({ id, original_filename: id + '.csv', status: 'COMPLETED',
    source_name: 'Source', records_loaded: 1, records_failed: 0, file_hash: '123', uploaded_at: '2026-10-19T12:00:00Z' });
  const rows = (id: string) => [{ id, raw_payload: { value: id + ' raw value' }, source_position: { line_start: 2 } }];
  const fetch = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
    if (url.includes('/records')) {
      if (url.includes('/second/')) return Promise.resolve(response(rows('second')));
      return new Promise<Response>((resolve, reject) => {
        const signal = options?.signal;
        const abort = () => { window.clearTimeout(timer); aborted(); reject(new DOMException('Aborted', 'AbortError')); };
        const timer = window.setTimeout(() => {
          signal?.removeEventListener('abort', abort);
          resolve(response(rows('first')));
        }, 2500);
        signal?.addEventListener('abort', abort, { once: true });
      });
    }
    if (url.includes('/errors') || url.includes('/sources')) return Promise.resolve(response([]));
    if (url.endsWith('/first')) return Promise.resolve(response(batch('first')));
    if (url.endsWith('/second')) return Promise.resolve(response(batch('second')));
    return Promise.resolve(response([batch('first'), batch('second')]));
  });
  vi.stubGlobal('fetch', fetch);
  return { fetch, aborted };
}

it('shows metadata immediately and finishes a records request slower than polling', async () => {
  vi.useFakeTimers();
  const { fetch, aborted } = delayedRecords();
  await act(async () => { render(<Imports user={viewer} onSessionExpired={vi.fn()} />); });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'first.csv' })); });
  expect(screen.getByRole('region', { name: 'Карточка импорта' })).toHaveTextContent('first.csv');
  expect(screen.queryByText(/first raw value/)).not.toBeInTheDocument();
  await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
  expect(screen.getByText(/first raw value/)).toBeInTheDocument();
  expect(aborted).not.toHaveBeenCalled();
  expect(fetch.mock.calls.filter(([url]) => url.includes('/first/records'))).toHaveLength(1);
});

it('cancels old records on navigation and never shows them in the new batch', async () => {
  vi.useFakeTimers();
  const { aborted } = delayedRecords();
  await act(async () => { render(<Imports user={viewer} onSessionExpired={vi.fn()} />); });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'first.csv' })); });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'second.csv' })); });
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
  expect(aborted).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('region', { name: 'Карточка импорта' })).toHaveTextContent('second.csv');
  expect(screen.getByText(/second raw value/)).toBeInTheDocument();
  expect(screen.queryByText(/first raw value/)).not.toBeInTheDocument();
});
