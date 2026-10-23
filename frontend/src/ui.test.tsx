import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StatusBadge, DataValue, EmptyState } from './ui';
import { App } from './App';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('shows a readable status and its canonical code without relying on color', () => {
  render(<StatusBadge value="POSSIBLE_MATCH" />);
  expect(screen.getByText('Требует проверки')).toBeVisible();
  expect(screen.getByText('POSSIBLE_MATCH')).toBeVisible();
});
it('renders structured source values as fields and safely escapes hostile text', () => {
  render(<DataValue value={{ mass: '12.5 kg', note: '<script>alert(1)</script>' }} />);
  expect(screen.getByText('mass')).toBeVisible();
  expect(screen.getByText('12.5 kg')).toBeVisible();
  expect(screen.getByText('<script>alert(1)</script>')).toBeVisible();
  expect(document.querySelector('script')).toBeNull();
});
it('explains an empty state with a usable next step', () => {
  render(<EmptyState title="Нет результатов">Загрузите два источника.</EmptyState>);
  expect(screen.getByRole('heading', { name: 'Нет результатов' })).toBeVisible();
  expect(screen.getByText('Загрузите два источника.')).toBeVisible();
});
function mockUser(permissions: string[]) {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (path: string) => new Response(JSON.stringify(path.endsWith('/me') ? { id: 'user', login: 'reader', display_name: 'Наблюдатель', roles: ['VIEWER'], permissions } : path.endsWith('/users') ? [] : { status: 'ok', components: { api: 'ok', database: 'ok', redis: 'ok' } }), { status: 200 })));
}
it('keeps the active navigation explicit and hides administrative navigation for a viewer', async () => {
  mockUser(['dashboard.view', 'import.view', 'match.view', 'conflict.view']);
  render(<App />);
  const overview = await screen.findByRole('button', { name: 'Состояние сервера' });
  expect(overview).toHaveAttribute('aria-current', 'page');
  expect(screen.queryByRole('button', { name: 'Пользователи' })).not.toBeInTheDocument();
  expect(screen.getByRole('navigation', { name: 'Разделы приложения' })).toBeVisible();
});
it('shows users separately while withholding creation from a view-only permission set', async () => {
  mockUser(['dashboard.view', 'user.view']);
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Пользователи' }));
  expect(await screen.findByRole('heading', { name: 'Пользователи', level: 1 })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Создать пользователя' })).not.toBeInTheDocument();
});
it('provides a clear permission-denied screen without invented actions', async () => {
  mockUser([]);
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Доступ не назначен' })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Импорт данных' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Выйти' })).toBeVisible();
});
it('shows a user-list load error even without management permission', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (path: string) => new Response(JSON.stringify(path.endsWith('/me') ? { id: 'user', login: 'reader', display_name: 'Наблюдатель', roles: ['VIEWER'], permissions: ['user.view'] } : {}), { status: path.endsWith('/users') ? 503 : 200 })));
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Пользователи' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить пользователей.');
});
