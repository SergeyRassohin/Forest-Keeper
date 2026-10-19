export interface Health {
  status: 'ok' | 'degraded';
  components: Record<'api' | 'database' | 'redis', 'ok' | 'unavailable'>;
}

export class SessionExpired extends Error {}

export async function readHealth(signal: AbortSignal): Promise<Health> {
  const response = await fetch('/api/v1/dashboard', {
    signal,
    cache: 'no-store',
  });
  if (response.status === 401) throw new SessionExpired();
  if (!response.ok && response.status !== 503)
    throw new Error('Сервер недоступен');
  const body: unknown = await response.json();
  if (!body || typeof body !== 'object')
    throw new Error('Некорректный ответ сервера');
  const health = body as Partial<Health>;
  if (
    !['ok', 'degraded'].includes(health.status ?? '') ||
    !health.components ||
    !['api', 'database', 'redis'].every((key) =>
      ['ok', 'unavailable'].includes(
        health.components![key as keyof Health['components']],
      ),
    )
  )
    throw new Error('Некорректный ответ сервера');
  return health as Health;
}

export interface User {
  id: string;
  login: string;
  display_name: string;
  roles: string[];
  permissions: string[];
}

export async function currentUser(signal: AbortSignal): Promise<User | null> {
  const response = await fetch('/api/v1/auth/me', {
    signal,
    cache: 'no-store',
  });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error('Не удалось проверить сессию');
  return response.json() as Promise<User>;
}

export async function signIn(login: string, password: string): Promise<User> {
  let response: Response;
  try {
    response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login, password }),
    });
  } catch {
    throw new Error('Не удалось подключиться к серверу. Повторите попытку.');
  }
  if (!response.ok) {
    if (response.status === 429)
      throw new Error('Слишком много попыток. Попробуйте позже.');
    if (response.status === 401) throw new Error('Неверный логин или пароль.');
    throw new Error('Вход временно недоступен. Повторите попытку.');
  }
  // The session is stored only in the HttpOnly cookie managed by the browser.
  const body: { user: User } = await response.json();
  return body.user;
}

export async function signOut(): Promise<void> {
  const response = await fetch('/api/v1/auth/logout', { method: 'POST' });
  if (!response.ok && response.status !== 401)
    throw new Error('Не удалось выйти. Повторите попытку.');
}
