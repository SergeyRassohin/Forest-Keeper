import { useEffect, useState } from 'react';
import { readHealth, type Health } from './api';

const labels = { api: 'API', database: 'PostgreSQL · pgvector', redis: 'Redis' };

export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    const timer = setTimeout(() => controller.abort(), 5000);
    readHealth(controller.signal)
      .then((result) => { if (!disposed) setHealth(result); })
      .catch(() => { if (!disposed) setError('Не удалось проверить сервер. Повторите проверку.'); })
      .finally(() => { if (!disposed) setLoading(false); clearTimeout(timer); });
    return () => { disposed = true; controller.abort(); clearTimeout(timer); };
  }, [attempt]);

  function retry() {
    setLoading(true);
    setError(null);
    setHealth(null);
    setAttempt((current) => current + 1);
  }

  return (
    <div className="shell">
      <header><span className="brand-mark" aria-hidden="true">FK</span><span>Forest Keeper</span><span className="release">MVP · 0.1</span></header>
      <main>
        <p className="eyebrow">Состояние среды</p>
        <h1>Основа для доверия к данным</h1>
        <p className="intro">Forest Keeper сравнивает источники, сохраняет происхождение данных и помогает принимать объяснимые решения.</p>
        <section aria-labelledby="health-title" className="panel">
          <div className="panel-heading"><h2 id="health-title">Готовность сервера</h2><button disabled={loading} onClick={retry}>Проверить снова</button></div>
          <div role="status" aria-live="polite">
            {loading && <p>Проверяем подключение…</p>}
            {error && <p className="warning">{error}</p>}
            {health && <>
              <p className={health.status === 'ok' ? 'healthy' : 'warning'}>{health.status === 'ok' ? 'Сервер готов' : 'Часть компонентов недоступна'}</p>
              <dl className="components">{Object.entries(labels).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{health.components[key as keyof Health['components']] === 'ok' ? 'Доступен' : 'Недоступен'}</dd></div>)}</dl>
            </>}
          </div>
        </section>
        <section className="next" aria-labelledby="next-title"><h2 id="next-title">Следующий шаг — первый сценарий</h2><p>Импорт двух источников → сравнение → конфликт → решение человека → рекомендация для похожего случая.</p><p>Импорт, Human Review и рекомендации появятся в следующих итерациях. Бизнес-данные пока не обрабатываются.</p></section>
      </main>
      <footer>Исходные данные сохраняются. Окончательное решение принимает человек.</footer>
    </div>
  );
}
