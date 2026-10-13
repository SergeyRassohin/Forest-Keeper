import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';

const viewer = {
  id: 'viewer',
  login: 'viewer',
  display_name: 'Наблюдатель',
  roles: ['VIEWER'],
  permissions: ['dashboard.view'],
};
const healthy = {
  status: 'ok',
  components: { api: 'ok', database: 'ok', redis: 'ok' },
};
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
afterEach(() => vi.unstubAllGlobals());

describe('authentication', () => {
  it('returns to sign-in when the server expires the session', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockImplementation((url: string) =>
          Promise.resolve(
            url.endsWith('/me') ? response(viewer) : response({}, 401),
          ),
        ),
    );
    render(<App />);
    expect(
      await screen.findByRole('heading', { name: 'Вход в Forest Keeper' }),
    ).toBeInTheDocument();
  });
  it('shows sign-in to an anonymous user and rejects bad credentials', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(response({}, 401))
        .mockResolvedValueOnce(response({}, 401)),
    );
    render(<App />);
    await screen.findByRole('heading', { name: 'Вход в Forest Keeper' });
    fireEvent.change(screen.getByLabelText('Логин'), {
      target: { value: 'viewer' },
    });
    fireEvent.change(screen.getByLabelText('Пароль'), {
      target: { value: 'incorrect' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Неверный логин или пароль.',
    );
    expect(screen.getByLabelText('Пароль')).toHaveValue('');
  });
  it('uses the cookie session and keeps admin controls out of viewer UI', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockImplementation((url: string) =>
          Promise.resolve(response(url.endsWith('/me') ? viewer : healthy)),
        ),
    );
    render(<App />);
    await screen.findByText('Сервер готов');
    expect(
      screen.queryByRole('heading', { name: 'Пользователи' }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Наблюдатель/)).toBeInTheDocument();
  });
  it('does not turn a network failure into an anonymous session', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    render(<App />);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Не удалось подключиться к серверу.',
    );
    expect(
      screen.queryByRole('button', { name: 'Войти' }),
    ).not.toBeInTheDocument();
  });
  it('returns to sign-in only after successful logout', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.endsWith('/logout'))
          return Promise.resolve(new Response(null, { status: 204 }));
        return Promise.resolve(
          response(url.endsWith('/me') ? viewer : healthy),
        );
      }),
    );
    render(<App />);
    await screen.findByText('Сервер готов');
    fireEvent.click(screen.getByRole('button', { name: 'Выйти' }));
    expect(
      await screen.findByRole('heading', { name: 'Вход в Forest Keeper' }),
    ).toBeInTheDocument();
  });
});
