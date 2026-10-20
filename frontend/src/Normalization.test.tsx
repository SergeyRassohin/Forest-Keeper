import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Normalization } from './Normalization';

const viewer = { id: 'v', login: 'v', display_name: 'Viewer', roles: ['VIEWER'], permissions: ['analysis.view'] };
const profile = { id: 'profile', code: 'synthetic-material', version: '1', synthetic: true };
const run = { id: 'run', status: 'COMPLETED', template_id: 'profile', mapping_hash: 'sha256', records_processed: 1, values_processed: 1, quality_counts: { VALID: 1 }, error_text: null, mapping_snapshot: { version: '1', engine_version: 'fk-normalization/1', bindings: [{ fields: [{ attribute_code: 'mass', path: ['mass'] }] }] } };
const record = { raw_record_id: 'raw', source_record_key: '001', source_position: { line_start: 2 }, raw_payload: { mass: '12,5 кг' }, source: { name: 'Source', code: 'source' }, import_batch: { id: 'batch', original_filename: 'source.csv', file_hash: 'original-sha' }, entity: { id: 'entity', domain: 'synthetic-material', entity_type: 'Material', display_name: 'Болт' }, values: [{ id: 'value', attribute_code: 'mass', raw_value: '12,5 кг', normalized_value: '12.5', unit: 'kg', quality_status: 'VALID', rule_definition: { path: ['mass'], kind: 'quantity' }, normalization_rule: { mapping: 'sha256', field: 'mass', presence: 'present', code: 'OK', conversion: { factor: '1' } } }], mapping_details: { code: 'OK', unmapped_fields: ['unknown'] } };
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

function install(slow = false) {
  const aborted = vi.fn();
  const fetch = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
    if (url.includes('/profiles')) return Promise.resolve(response([profile]));
    if (url.includes('import_batch_id=')) return Promise.resolve(response([run]));
    if (url.includes('/records') && slow) return new Promise<Response>((resolve, reject) => {
      const timer = window.setTimeout(() => resolve(response([record])), 2500);
      options?.signal?.addEventListener('abort', () => { window.clearTimeout(timer); aborted(); reject(new DOMException('Aborted', 'AbortError')); }, { once: true });
    });
    if (url.includes('/records')) return Promise.resolve(response([record]));
    return Promise.resolve(response(run));
  });
  vi.stubGlobal('fetch', fetch);
  return { fetch, aborted };
}

it('shows source, raw, normalized, unit, quality and exact rule without offering a viewer mutation', async () => {
  install();
  render(<Normalization batchId="batch" importReady user={viewer} onSessionExpired={vi.fn()} />);
  expect(await screen.findByRole('status')).toBeInTheDocument();
  fireEvent.click(await screen.findByText('Запись 001 · Болт'));
  const row = screen.getAllByRole('row')[0].querySelector('th');
  expect(row).toHaveTextContent('Канонический');
  const valueRow = screen.getAllByRole('row')[1];
  expect(within(valueRow).getByText('"12,5 кг"')).toBeInTheDocument();
  expect(within(valueRow).getByText('"12.5"')).toBeInTheDocument();
  expect(valueRow).toHaveTextContent('VALID');
  expect(valueRow).toHaveTextContent('quantity');
  expect(screen.getByText(/Источник: Source/)).toBeInTheDocument();
  expect(screen.getByText(/Поля без mapping \(UNKNOWN\): unknown/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Нормализовать пакет' })).not.toBeInTheDocument();
});

it('uses the existing analysis API for explicit user runs', async () => {
  const { fetch } = install();
  const user = { ...viewer, permissions: ['analysis.view', 'analysis.run'] };
  render(<Normalization batchId="batch" importReady user={user} onSessionExpired={vi.fn()} />);
  const button = screen.getByRole('button', { name: 'Нормализовать пакет' });
  await vi.waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  await vi.waitFor(() => expect(fetch.mock.calls.some(([url, options]) => url === '/api/v1/analysis' && options?.method === 'POST')).toBe(true));
  const request = fetch.mock.calls.find(([, options]) => options?.method === 'POST')!;
  expect(JSON.parse(request[1].body)).toEqual({ import_batch_ids: ['batch'], template_id: 'profile' });
});

it('finishes slow result reads without aborting them at the polling interval', async () => {
  vi.useFakeTimers();
  const { aborted } = install(true);
  await act(async () => { render(<Normalization batchId="batch" importReady user={viewer} onSessionExpired={vi.fn()} />); });
  expect(screen.getByRole('status')).toBeInTheDocument();
  await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
  expect(screen.getByText('Запись 001 · Болт')).toBeInTheDocument();
  expect(aborted).not.toHaveBeenCalled();
});

it('expires sessions and cancels inflight reads when leaving the screen', async () => {
  const expired = vi.fn();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({}, 401)));
  const first = render(<Normalization batchId="batch" importReady user={viewer} onSessionExpired={expired} />);
  await vi.waitFor(() => expect(expired).toHaveBeenCalled());
  first.unmount();
  const { aborted } = install(true);
  const second = render(<Normalization batchId="batch" importReady user={viewer} onSessionExpired={vi.fn()} />);
  await screen.findByRole('status');
  second.unmount();
  expect(aborted).toHaveBeenCalled();
});
