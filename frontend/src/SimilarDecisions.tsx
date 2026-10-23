import { useEffect, useState } from 'react';
import { requestJson, SessionExpired } from './api';
import { DataValue, Identifier, StatusBadge } from './ui';

type Precedent = {
  decision_id: string; conflict_id: string; similarity: number; matched_features: string[];
  mismatched_features: string[]; actor: { display_name: string }; decided_at: string;
  outcome: string; selected_value: unknown; unit: string | null; reason: string;
  domain: string; entity_type: string; attribute_code: string;
  evidence_summary?: { subject: string; observations: { value: string | null; presence: string; quality: string; source_type: string; source_role: string }[]; known_unknowns: string[] };
};
type Retrieval = {
  state: 'READY' | 'NO_PRECEDENT' | 'INDEXING' | 'UNAVAILABLE'; reason_code: string;
  results: Precedent[]; embedding_model: { is_test: boolean } | null;
};
const labels: Record<string, string> = {
  domain: 'Область данных', entity_type: 'Тип сущности', attribute_code: 'Атрибут',
  conflict_type: 'Тип расхождения', value_kind: 'Тип значения', unit: 'Единица измерения',
  subject: 'Наименование', observations: 'Значения и источники', matching: 'Контекст сопоставления',
  normalization: 'Контекст нормализации', authority: 'Авторитетный источник', forest_codex: 'Forest Codex',
};

export function SimilarDecisions({ conflictId, onSessionExpired, onOpenDecision }: {
  conflictId: string; onSessionExpired: () => void; onOpenDecision?: (id: string) => void;
}) {
  const [data, setData] = useState<Retrieval | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    requestJson<Retrieval>(`/conflicts/${conflictId}/similar-decisions`, { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) setData(value); })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        if (cause instanceof SessionExpired) onSessionExpired();
        else setError('Не удалось загрузить прошлые решения. Повторите поиск.');
      });
    return () => controller.abort();
  }, [conflictId, attempt, onSessionExpired]);
  return <section className="precedent-panel" aria-label="Похожие прошлые решения">
    <h3>Похожие прошлые решения</h3>
    <p className="human-boundary">Похожие решения показывают прошлый опыт. Они не являются автоматическим решением текущего конфликта.</p>
    {!data && !error && <p role="status">Ищем прошлые подтверждённые решения…</p>}
    {error && <p role="alert">{error}</p>}
    {data?.embedding_model?.is_test && <p className="warning">Тестовый поиск на синтетических данных. Качество поиска на рабочих данных ещё не подтверждено.</p>}
    {data?.state === 'UNAVAILABLE' && <p role="status">Поиск временно недоступен. История решений и рассмотрение конфликта доступны.</p>}
    {data?.state === 'INDEXING' && <p role="status">Индекс ещё строится. Повторите поиск позже.</p>}
    {data?.state === 'NO_PRECEDENT' && <p role="status">{data.reason_code === 'NO_ACCESSIBLE_PRECEDENT' ? 'Нет доступных решений в вашей области данных.' : 'Похожих подтверждённых решений пока нет.'}</p>}
    {data?.results.map((item) => <article className="source-card" key={item.decision_id}>
      <p className="eyebrow">Похожесть {(item.similarity * 100).toFixed(2)}%</p>
      <StatusBadge value={item.outcome} />
      <p>Область: {item.domain} · Тип сущности: {item.entity_type} · Атрибут: {item.attribute_code} · Единица: {item.unit ?? 'Без единицы'}</p>
      <p><DataValue value={item.selected_value} /> {item.unit}</p>
      <p>{item.actor.display_name} · {new Date(item.decided_at).toLocaleString()}</p>
      <p>{item.reason}</p>
      <p>Совпало: {item.matched_features.map((key) => labels[key] ?? key).join(', ')}</p>
      {!!item.mismatched_features.length && <p>Различается: {item.mismatched_features.map((key) => labels[key] ?? key).join(', ')}</p>}
      <p>Случай прошёл проверку совместимости области, типа сущности, атрибута и единицы. Оценка отражает сходство контекста.</p>
      {item.evidence_summary && <details><summary>Исторические значения и ограничения</summary>
        <p>Наименование: {item.evidence_summary.subject}</p>
        <ul>{item.evidence_summary.observations.map((value, index) => <li key={index}><DataValue value={value.value} /> {item.unit} · {value.source_type} · Наличие: {value.presence} · Качество: {value.quality} · Роль: {value.source_role}</li>)}</ul>
        <p>Не определено: {item.evidence_summary.known_unknowns.join(', ')}</p>
      </details>}
      <Identifier>Decision: {item.decision_id}</Identifier><br />
      <Identifier>Исходный конфликт: {item.conflict_id}</Identifier>
      {onOpenDecision && <button onClick={() => onOpenDecision(item.decision_id)}>Открыть прошлое решение</button>}
    </article>)}
    <button onClick={() => { setData(null); setError(''); setAttempt((value) => value + 1); }}>Повторить поиск</button>
  </section>;
}
