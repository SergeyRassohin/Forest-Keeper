import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Imports } from './Imports';

const viewer = { id: 'v', login: 'v', display_name: 'Viewer', roles: ['VIEWER'], permissions: ['source.view', 'import.view'] };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
afterEach(() => vi.unstubAllGlobals());

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
