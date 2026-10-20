import { useCallback, useEffect, useState, type FormEvent } from 'react';
import {
  currentUser,
  readHealth,
  SessionExpired,
  signIn,
  signOut,
  type Health,
  type User,
} from './api';
import { UserAdmin } from './UserAdmin';
import { Imports } from './Imports';

const labels = {
  api: 'API',
  database: 'PostgreSQL · pgvector',
  redis: 'Redis',
};

export function HealthDashboard({
  onSessionExpired,
}: {
  onSessionExpired?: () => void;
}) {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    const timer = setTimeout(() => controller.abort(), 5000);
    readHealth(controller.signal)
      .then((result) => {
        if (!disposed) setHealth(result);
      })
      .catch((cause) => {
        if (disposed) return;
        if (cause instanceof SessionExpired && onSessionExpired)
          onSessionExpired();
        else setError('Не удалось проверить сервер. Повторите проверку.');
      })
      .finally(() => {
        if (!disposed) setLoading(false);
        clearTimeout(timer);
      });
    return () => {
      disposed = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, [attempt, onSessionExpired]);

  function retry() {
    setLoading(true);
    setError(null);
    setHealth(null);
    setAttempt((current) => current + 1);
  }

  return (
    <div className="shell">
      <main>
        <p className="eyebrow">Состояние среды</p>
        <h1>Основа для доверия к данным</h1>
        <p className="intro">
          Forest Keeper сравнивает источники, сохраняет происхождение данных и
          помогает принимать объяснимые решения.
        </p>
        <section aria-labelledby="health-title" className="panel">
          <div className="panel-heading">
            <h2 id="health-title">Готовность сервера</h2>
            <button disabled={loading} onClick={retry}>
              Проверить снова
            </button>
          </div>
          <div role="status" aria-live="polite">
            {loading && <p>Проверяем подключение…</p>}
            {error && <p className="warning">{error}</p>}
            {health && (
              <>
                <p className={health.status === 'ok' ? 'healthy' : 'warning'}>
                  {health.status === 'ok'
                    ? 'Сервер готов'
                    : 'Часть компонентов недоступна'}
                </p>
                <dl className="components">
                  {Object.entries(labels).map(([key, label]) => (
                    <div key={key}>
                      <dt>{label}</dt>
                      <dd>
                        {health.components[
                          key as keyof Health['components']
                        ] === 'ok'
                          ? 'Доступен'
                          : 'Недоступен'}
                      </dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
          </div>
        </section>
        <section className="next" aria-labelledby="next-title">
          <h2 id="next-title">Исходные и нормализованные данные</h2>
          <p>
            В разделе «Импорт данных» можно загрузить CSV, XLSX и XML,
            посмотреть исходные записи и результат нормализации с его правилом и происхождением.
          </p>
          <p>
            Следующий этап — сопоставление записей.
            Сопоставление, разбор конфликтов и рекомендации будут добавлены позже.
          </p>
        </section>
      </main>
    </div>
  );
}

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [failure, setFailure] = useState(false);
  const [retry, setRetry] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [page, setPage] = useState('dashboard');
  const expire = useCallback(() => setUser(null), []);

  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    const timer = setTimeout(() => controller.abort(), 5000);
    currentUser(controller.signal)
      .then((result) => {
        if (!disposed) setUser(result);
      })
      .catch(() => {
        if (!disposed) setFailure(true);
      })
      .finally(() => {
        clearTimeout(timer);
        if (!disposed) setChecking(false);
      });
    return () => {
      disposed = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, [retry]);

  async function enter(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      setUser(await signIn(login, password));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось войти.');
    } finally {
      setPassword('');
      setBusy(false);
    }
  }

  async function leave() {
    setBusy(true);
    setError('');
    try {
      await signOut();
      setUser(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось выйти.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="shell">
        <span className="brand-mark" aria-hidden="true">
          FK
        </span>
        <span>Forest Keeper</span>
        {user && (
          <>
            <span className="identity">
              {user.display_name} · {user.roles.join(', ')}
            </span>
            <button onClick={leave} disabled={busy}>
              Выйти
            </button>
          </>
        )}
      </header>
      {checking ? (
        <main className="shell" role="status">
          Проверяем сессию…
        </main>
      ) : failure ? (
        <main className="shell">
          <p role="alert">Не удалось подключиться к серверу.</p>
          <button
            onClick={() => {
              setChecking(true);
              setFailure(false);
              setRetry(retry + 1);
            }}
          >
            Повторить
          </button>
        </main>
      ) : !user ? (
        <main className="shell">
          <section className="panel login-panel">
            <h1>Вход в Forest Keeper</h1>
            <p>Войдите, чтобы работать с доступными вам данными.</p>
            <form onSubmit={enter}>
              <label>
                Логин
                <input
                  autoComplete="username"
                  required
                  value={login}
                  onChange={(event) => setLogin(event.target.value)}
                  maxLength={64}
                />
              </label>
              <label>
                Пароль
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  maxLength={128}
                />
              </label>
              {error && (
                <p role="alert" className="warning">
                  {error}
                </p>
              )}
              <button disabled={busy}>{busy ? 'Входим…' : 'Войти'}</button>
            </form>
          </section>
        </main>
      ) : (
        <>
          {error && (
            <p className="shell warning" role="alert">
              {error}
            </p>
          )}
          <nav className="shell" aria-label="Разделы приложения">
            <button onClick={() => setPage('dashboard')}>Состояние сервера</button>
            {user.permissions.includes('import.view') &&
              <button onClick={() => setPage('imports')}>Импорт данных</button>}
          </nav>
          {page === 'imports' && user.permissions.includes('import.view') ? (
            <Imports user={user} onSessionExpired={expire} />
          ) : user.permissions.includes('dashboard.view') ? (
            <HealthDashboard onSessionExpired={expire} />
          ) : (
            <main className="shell">
              <h1>Доступ не назначен</h1>
              <p>Обратитесь к администратору для назначения роли.</p>
            </main>
          )}
          {page === 'dashboard' && user.permissions.includes('user.view') && <UserAdmin />}
        </>
      )}
      <footer className="shell">Исходные данные сохраняются. Окончательное решение принимает человек.</footer>
    </>
  );
}
