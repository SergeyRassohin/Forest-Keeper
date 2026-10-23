import { Decisions } from './Decisions';
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
import { Conflicts } from './Conflicts';
import { Matching } from './Matching';

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
        <h1>Обзор рабочего пространства</h1>
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
          <h2 id="next-title">Импорт, нормализация и сопоставление</h2>
          <p>
            В разделе «Импорт данных» можно загрузить CSV, XLSX и XML,
            посмотреть исходные записи и результат нормализации с его правилом и происхождением.
          </p>
          <p>
            В разделе «Сопоставление» видны пары записей, оценки и объяснения.
            В разделе «Конфликты» доступны расхождения значений и их происхождение. Рекомендации и решения человека относятся к следующим этапам.
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
  const [conflictMatchingId, setConflictMatchingId] = useState('');
  const [decisionId, setDecisionId] = useState('');
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
      setPage('dashboard');
      setConflictMatchingId('');
      setDecisionId('');
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

  const sections = [
    { key: 'dashboard', label: 'Состояние сервера', caption: 'Обзор', permission: 'dashboard.view' },
    { key: 'imports', label: 'Импорт данных', caption: 'Источники и нормализация', permission: 'import.view' },
    { key: 'matching', label: 'Сопоставление', caption: 'Идентичность записей', permission: 'match.view' },
    { key: 'conflicts', label: 'Конфликты', caption: 'Расхождения значений', permission: 'conflict.view' },
    { key: 'decisions', label: 'Реестр решений', caption: 'Подтверждённая история', permission: 'decision.view' },
    { key: 'users', label: 'Пользователи', caption: 'Администрирование', permission: 'user.view' },
  ];
  const currentSection = sections.find((item) => item.key === page);
  const brand = <span className="brand"><img src="/brand/forest-keeper.svg" alt="" /><span>Forest Keeper<small>Порядок в корпоративных данных</small></span></span>;
  const signInForm = <section className="login-panel" aria-labelledby="login-title">
    <p className="eyebrow">Рабочее пространство</p>
    <h1 id="login-title">Вход в Forest Keeper</h1>
    <p>Войдите, чтобы сравнить источники и увидеть основания каждого результата.</p>
    <form onSubmit={enter}>
      <label>Логин<input autoComplete="username" required value={login} onChange={(event) => setLogin(event.target.value)} maxLength={64} /></label>
      <label>Пароль<input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} maxLength={128} /></label>
      {error && <p role="alert">{error}</p>}
      <button className="primary" disabled={busy}>{busy ? 'Входим…' : 'Войти'}</button>
    </form>
    <p className="login-footnote">Доступ определяется вашей ролью. Исходные данные сохраняются.</p>
  </section>;

  if (!user) return <><a className="skip-link" href="#main-content">Перейти к содержимому</a><main className="login-layout" id="main-content">
    <aside className="login-brand" aria-label="Forest Keeper">{brand}<div><p className="brand-tagline">Ясность там, где данные расходятся.</p><p>Два источника. Объяснимое сравнение. Решение остаётся за человеком.</p></div><p>FOREST KEEPER · WEB CLIENT</p></aside>
    {checking ? <section className="login-panel" role="status"><h1>Проверяем сессию…</h1><p>Подключаем ваше рабочее пространство.</p></section> : failure ? <section className="login-panel"><h1>Подключение недоступно</h1><p role="alert">Не удалось подключиться к серверу.</p><button onClick={() => { setChecking(true); setFailure(false); setRetry(retry + 1); }}>Повторить</button></section> : signInForm}
  </main></>;

  return <><a className="skip-link" href="#main-content">Перейти к содержимому</a><div className="app-frame">
    <aside className="app-sidebar">{brand}
      <nav className="app-nav" aria-label="Разделы приложения">{sections.filter((item) => user.permissions.includes(item.permission)).map((item, index) => <button key={item.key} aria-current={page === item.key ? 'page' : undefined} onClick={() => { setPage(item.key); if (item.key === 'decisions') setDecisionId(''); }}><span className="nav-index" aria-hidden="true">0{index + 1}</span>{item.label}</button>)}</nav>
      <div className="sidebar-note">Источники сохраняются.<br />Основания доступны.<br />Решение принимает человек.</div>
    </aside>
    <div className="app-workspace">
      <header className="workspace-header"><span className="workspace-title"><small>Рабочее пространство</small>{currentSection?.caption ?? 'Обзор'}</span><span className="identity">{user.display_name}<small>{user.roles.join(' · ')}</small></span><button onClick={leave} disabled={busy}>Выйти</button></header>
      <div className="workspace-content" id="main-content" tabIndex={-1}>
        {error && <p className="shell" role="alert">{error}</p>}
        {page === 'conflicts' && user.permissions.includes('conflict.view') ? <Conflicts user={user} onSessionExpired={expire} initialRunId={conflictMatchingId} onOpenDecision={(id) => { setDecisionId(id); setPage('decisions'); }} /> : page === 'matching' && user.permissions.includes('match.view') ? <Matching user={user} onSessionExpired={expire} onConflicts={(id) => { setConflictMatchingId(id); setPage('conflicts'); }} /> : page === 'imports' && user.permissions.includes('import.view') ? <Imports user={user} onSessionExpired={expire} /> : page === 'decisions' && user.permissions.includes('decision.view') ? <Decisions onSessionExpired={expire} initialId={decisionId} /> : page === 'users' && user.permissions.includes('user.view') ? <UserAdmin canManage={user.permissions.includes('user.manage') && user.permissions.includes('role.assign')} /> : user.permissions.includes('dashboard.view') ? <HealthDashboard onSessionExpired={expire} /> : <main className="shell"><p className="eyebrow">Права доступа</p><h1>Доступ не назначен</h1><p>Обратитесь к администратору для назначения роли.</p></main>}
      </div>
      <footer className="shell workspace-footer">Исходные данные сохраняются. Окончательное решение принимает человек.</footer>
    </div>
  </div></>;
}
