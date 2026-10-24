import { useEffect, useState } from 'react';
import { requestJson as api, SessionExpired } from './api';
import { type Decision, outcomeLabels } from './decisionTypes';
import { DataValue, EmptyState, Identifier, StatusBadge } from './ui';

export function DecisionCard({ decision, title = 'Сохранённое решение' }: { decision: Decision; title?: string }) {
  return <article className="panel decision-card" aria-label="Карточка решения">
    <p className="eyebrow">Decision Registry · подтверждено человеком</p>
    <div className="panel-heading"><h2>{title}</h2><StatusBadge value={decision.status} label={decision.status === 'ACTIVE' ? 'Действует' : 'Заменено'} /></div>
    <h3>{decision.business_key} · {decision.attribute_code}</h3>
    <p>{outcomeLabels.get(decision.decision_type) ?? decision.decision_type}</p>
    {['SELECT_VALUE', 'ENTER_VALUE'].includes(decision.decision_type) && <div className="compared-value"><DataValue value={decision.selected_value} /> {decision.unit}</div>}
    <dl><dt>Обоснование человека</dt><dd className="human-reason">{decision.reason}</dd>
      <dt>Кто и когда</dt><dd>{decision.actor_display_name}<br /><Identifier>{decision.user_id}</Identifier> · {new Date(decision.decided_at).toLocaleString()} · {decision.actor_roles.join(' · ')}</dd>
      <dt>Идентификатор решения</dt><dd><Identifier>{decision.id}</Identifier></dd>
      {decision.supersedes_decision_id && <><dt>Заменяет решение</dt><dd><Identifier>{decision.supersedes_decision_id}</Identifier></dd></>}
      {decision.superseded_by && <><dt>Заменено решением</dt><dd><Identifier>{decision.superseded_by}</Identifier></dd></>}
    </dl>
    {decision.context_snapshot !== undefined && <details><summary>Исторический контекст и происхождение решения</summary>
      <p>Контекст сохранён на момент рассмотрения; исходные значения не переписаны.</p>
      <p>Контрольная сумма evidence: <Identifier>{decision.evidence_hash}</Identifier></p>
      <p>Версия рассмотрения: <Identifier>{decision.context_version}</Identifier></p>
      <pre>{JSON.stringify(decision.context_snapshot, null, 2)}</pre>
      {decision.corrected_input !== null && decision.corrected_input !== undefined && <><h3>Введённое значение и преобразование</h3><DataValue value={decision.corrected_input} /><pre>{JSON.stringify(decision.conversion_trace, null, 2)}</pre></>}
    </details>}
    <p className="human-boundary">Решение сохранено в Forest Keeper. Исходные системы не изменялись.</p>
  </article>;
}

export function Decisions({ onSessionExpired, initialId = '', onReturnConflict }: { onSessionExpired: () => void; initialId?: string; onReturnConflict?: () => void }) {
  const [items, setItems] = useState<Decision[]>([]);
  const [selected, setSelected] = useState(initialId);
  const [detail, setDetail] = useState<Decision | null>(null);
  const [history, setHistory] = useState<Decision[]>([]);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [offset, setOffset] = useState(0);
  const [outcome, setOutcome] = useState('');
  const [status, setStatus] = useState('');
  const [attribute, setAttribute] = useState('');
  const [businessKey, setBusinessKey] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: '50', offset: String(offset) });
    if (outcome) params.set('decision_type', outcome);
    if (status) params.set('status', status);
    if (attribute) params.set('attribute_code', attribute);
    if (businessKey) params.set('business_key', businessKey);
    async function load() {
      try {
        const [list, card] = await Promise.all([api<Decision[]>('/decisions?' + params, { signal: controller.signal }),
          selected ? api<Decision>('/decisions/' + selected, { signal: controller.signal }) : Promise.resolve(null)]);
        const timeline = card ? await api<Decision[]>(`/conflicts/${card.conflict_id}/decisions?limit=50&offset=${historyOffset}`, { signal: controller.signal }) : [];
        if (!controller.signal.aborted) { setItems(list); setDetail(card); setHistory(timeline); setLoaded(true); setError(''); }
      } catch (cause) {
        if (!controller.signal.aborted) {
          if (cause instanceof SessionExpired) onSessionExpired();
          else { setError(cause instanceof Error ? cause.message : 'Не удалось загрузить решения.'); setDetail(null); setHistory([]); }
        }
      }
    }
    void load();
    return () => controller.abort();
  }, [selected, outcome, status, attribute, businessKey, offset, historyOffset, onSessionExpired]);
  function clearDetail() { setSelected(''); setDetail(null); setHistoryOffset(0); setOffset(0); }
  return <main className="shell" aria-label="Реестр решений">
    {onReturnConflict && <button onClick={onReturnConflict}>Вернуться к текущему конфликту</button>}
    <p className="eyebrow">Подтверждённая история</p><h1>Реестр решений</h1>
    <p>Кто, что и почему решил. Исправления сохраняются новыми записями; предыдущие решения остаются в истории.</p>
    {error && <p role="alert">{error}</p>}
    <section className="panel" aria-label="Список решений"><h2>Решения человека</h2>
      <div className="review-filters"><label>Результат решения<select value={outcome} onChange={(event) => { setOutcome(event.target.value); clearDetail(); }}><option value="">Все результаты</option>{[...outcomeLabels].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Актуальность решения<select value={status} onChange={(event) => { setStatus(event.target.value); clearDetail(); }}><option value="">Вся история</option><option value="ACTIVE">Действующие</option><option value="SUPERSEDED">Заменённые</option></select></label>
        <label>Атрибут<input value={attribute} maxLength={64} onChange={(event) => { setAttribute(event.target.value); clearDetail(); }} /></label>
        <label>Ключ записи<input value={businessKey} maxLength={256} onChange={(event) => { setBusinessKey(event.target.value); clearDetail(); }} /></label></div>
      {!loaded && !error && <p role="status">Загружаем реестр решений…</p>}
      {loaded && !items.length && <EmptyState title="Сохранённых решений пока нет">Откройте конфликт и пройдите рассмотрение под ролью с правом принятия решений.</EmptyState>}
      {!!items.length && <div className="table-scroll" tabIndex={0} role="region" aria-label="Таблица решений"><table><thead><tr><th>Запись / атрибут</th><th>Решение</th><th>Актуальность</th><th>Когда</th><th>Подробности</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td>{item.business_key}<small className="record-key">{item.attribute_code}</small></td><td>{outcomeLabels.get(item.decision_type)}</td><td><StatusBadge value={item.status} label={item.status === 'ACTIVE' ? 'Действует' : 'Заменено'} /></td><td>{new Date(item.decided_at).toLocaleString()}</td><td><button aria-label={'Открыть решение ' + item.id} onClick={() => { setSelected(item.id); setDetail(null); setHistoryOffset(0); }}>Открыть решение</button><br /><Identifier>{item.id.slice(0, 8)}</Identifier></td></tr>)}</tbody></table></div>}
      <button disabled={!offset} onClick={() => { setSelected(''); setDetail(null); setHistoryOffset(0); setOffset(Math.max(0, offset - 50)); }}>Предыдущие решения</button><button disabled={items.length < 50} onClick={() => { setSelected(''); setDetail(null); setHistoryOffset(0); setOffset(offset + 50); }}>Следующие решения</button>
    </section>
    {detail && <><DecisionCard decision={detail} /><section className="panel" aria-label="История решений"><h2>История рассмотрения</h2><p>Conflict: <Identifier>{detail.conflict_id}</Identifier></p>
      <ol className="decision-timeline">{history.map((item) => <li key={item.id}><StatusBadge value={item.status} label={item.status === 'ACTIVE' ? 'Действует' : 'Заменено'} /><p>{outcomeLabels.get(item.decision_type)} · {new Date(item.decided_at).toLocaleString()}</p><p className="human-reason">{item.reason}</p><p>{item.actor_display_name} · <Identifier>{item.user_id}</Identifier></p>{item.supersedes_decision_id && <p>Заменяет: <Identifier>{item.supersedes_decision_id}</Identifier></p>}{item.superseded_by && <p>Заменено: <Identifier>{item.superseded_by}</Identifier></p>}<button aria-label={'Показать эту запись: историческое решение ' + item.id} onClick={() => { setSelected(item.id); setDetail(null); }}>Показать эту запись</button><Identifier>{item.id}</Identifier></li>)}</ol>
      <button disabled={!historyOffset} onClick={() => setHistoryOffset(Math.max(0, historyOffset - 50))}>Предыдущая история</button><button disabled={history.length < 50} onClick={() => setHistoryOffset(historyOffset + 50)}>Следующая история</button>
    </section></>}
  </main>;
}
