import { useEffect, useState, type FormEvent } from 'react';
import type { User } from './api';

const roles = ['VIEWER', 'REVIEWER', 'DATA_OWNER', 'ADMIN'];

export function UserAdmin({ canManage }: { canManage: boolean }) {
  const [loaded, setLoaded] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [login, setLogin] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [selected, setSelected] = useState<string[]>(['VIEWER']);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/v1/users', { signal: controller.signal, cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        return response.json() as Promise<User[]>;
      })
      .then((items) => { setUsers(items); setLoaded(true); })
      .catch(() => {
        if (!controller.signal.aborted)
          setError('Не удалось загрузить пользователей.');
      });
    return () => controller.abort();
  }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/v1/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          login,
          full_name: name,
          password,
          roles: selected,
        }),
      });
      if (!response.ok) {
        if (response.status === 403)
          throw new Error('Для управления пользователями войдите повторно.');
        if (response.status === 409)
          throw new Error('Этот логин уже используется.');
        if (response.status === 422)
          throw new Error(
            'Проверьте логин и пароль: пароль должен содержать от 12 до 128 символов.',
          );
        throw new Error('Не удалось создать пользователя.');
      }
      const created: User = await response.json();
      setUsers((current) => [...current, created]);
      setLogin('');
      setName('');
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Не удалось создать пользователя.',
      );
    } finally {
      setPassword('');
      setBusy(false);
    }
  }

  return (
    <main className="shell" aria-labelledby="users-title"><p className="eyebrow">Администрирование</p><h1 id="users-title">Пользователи</h1><p>Доступ к данным и действиям определяется назначенными ролями.</p>
      <div className="panel">
        <h2>Участники рабочего пространства</h2>
        {error && <p role="alert">{error}</p>}
        {!loaded && !error && <p role="status">Загружаем пользователей…</p>}
        <ul className="user-list">
          {users.map((user) => (
            <li key={user.id}>
              {user.display_name} · {user.login} · {user.roles.join(', ')}
            </li>
          ))}
        </ul>
        {canManage && <><h3>Создать пользователя</h3>
        <form onSubmit={create}>
          <label>
            Логин нового пользователя
            <input
              required
              minLength={3}
              maxLength={64}
              pattern="[A-Za-z0-9_.@\-]+"
              value={login}
              onChange={(event) => setLogin(event.target.value)}
            />
          </label>
          <label>
            Имя пользователя
            <input
              required
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label>
            Начальный пароль
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              maxLength={128}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <fieldset>
            <legend>Роли</legend>
            {roles.map((role) => (
              <label className="role-choice" key={role}>
                <input
                  type="checkbox"
                  checked={selected.includes(role)}
                  onChange={(event) =>
                    setSelected((current) =>
                      event.target.checked
                        ? [...current, role]
                        : current.filter((value) => value !== role),
                    )
                  }
                />
                {role}
              </label>
            ))}
          </fieldset>
          <p>
            ADMIN управляет системой. Для бизнес-решений отдельно нужны REVIEWER
            или DATA_OWNER.
          </p>
          <button disabled={busy}>Создать пользователя</button>
        </form></>}
      </div>
    </main>
  );
}
