import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';

function mockHealth(status: 'ok' | 'degraded') {
  return new Response(JSON.stringify({
    status, components: { api: 'ok', database: status === 'ok' ? 'ok' : 'unavailable', redis: 'ok' },
  }), { status: status === 'ok' ? 200 : 503 });
}

describe('server readiness', () => {
  it('shows actual dependency readiness', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockHealth('ok')));
    render(<App />);
    expect(await screen.findByText('Сервер готов')).toBeInTheDocument();
    expect(screen.getAllByText('Доступен')).toHaveLength(3);
  });

  it('shows degradation from a 503 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockHealth('degraded')));
    render(<App />);
    expect(await screen.findByText('Часть компонентов недоступна')).toBeInTheDocument();
    expect(screen.getByText('Недоступен')).toBeInTheDocument();
  });

  it('can retry a network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(mockHealth('ok')));
    render(<App />);
    expect(await screen.findByText(/Не удалось проверить сервер/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить снова' }));
    expect(await screen.findByText('Сервер готов')).toBeInTheDocument();
  });

  it('rejects malformed API data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"status":"ok"}')));
    render(<App />);
    expect(await screen.findByText(/Не удалось проверить сервер/)).toBeInTheDocument();
    expect(screen.queryByText('Сервер готов')).not.toBeInTheDocument();
  });
});
