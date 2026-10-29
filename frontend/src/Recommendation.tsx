import { useEffect, useRef, useState } from 'react';
import { ApiFailure, requestJson, SessionExpired } from './api';
import { outcomeLabels, type ReviewContext } from './decisionTypes';
import type { RecommendationResult } from './recommendationTypes';
import { DataValue, Identifier } from './ui';

const roleLabels = new Map([['ACCOUNTING_EXPORT', 'Учётная система'], ['REGISTER_EXPORT', 'Рабочий реестр']]);

export function Recommendation({ conflictId, contextVersion, currentValues, canUse, disabled,
  onUse, onInvalidated, onContextChanged, onOpenDecision, onSessionExpired }: {
  conflictId: string; contextVersion: string; currentValues: ReviewContext['selectable_values'];
  canUse: boolean; disabled: boolean; onUse: (result: RecommendationResult) => void;
  onInvalidated: () => void; onContextChanged: () => void;
  onOpenDecision?: (id: string) => void; onSessionExpired: () => void;
}) {
  const [data, setData] = useState<RecommendationResult | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const fingerprint = useRef('');
  const suspended = useRef(disabled);
  useEffect(() => {
    if (suspended.current && !disabled) setAttempt(value => value + 1);
    suspended.current = disabled;
  }, [disabled]);
  useEffect(() => {
    let controller = new AbortController();
    let disposed = false;
    async function load() {
      if (suspended.current) return;
      controller.abort(); controller = new AbortController();
      const signal = controller.signal;
      try {
        const result = await requestJson<RecommendationResult>(`/conflicts/${conflictId}/recommendation`, { signal });
        if (disposed || signal.aborted || suspended.current) return;
        if (result.review_context_version !== contextVersion) {
          setData(null); onInvalidated(); onContextChanged(); return;
        }
        if (fingerprint.current && fingerprint.current !== result.context_fingerprint) onInvalidated();
        fingerprint.current = result.context_fingerprint;
        setData(result); setError('');
      } catch (cause) {
        if (disposed || signal.aborted || suspended.current) return;
        setData(null); onInvalidated();
        if (cause instanceof SessionExpired) onSessionExpired();
        else setError(cause instanceof ApiFailure && [403, 404].includes(cause.status)
          ? 'Рекомендация недоступна в вашей области доступа.'
          : 'Не удалось проверить основания рекомендации. Ручное решение доступно отдельно.');
      }
    }
    void load();
    const timer = window.setInterval(() => { void load(); }, 30000);
    const refresh = () => { if (document.visibilityState !== 'hidden') void load(); };
    window.addEventListener('focus', refresh);
    return () => { disposed = true; controller.abort(); window.clearInterval(timer); window.removeEventListener('focus', refresh); };
  }, [conflictId, contextVersion, attempt, onInvalidated, onContextChanged, onSessionExpired]);
  return <section className="recommendation-panel" aria-label="Рекомендация Forest Keeper">
    <h3>Рекомендация Forest Keeper</h3>
    <p className="human-boundary">Это предложение на основе прошлых решений. Проверьте основания и примите собственное решение.</p>
    {!data && !error && <p role="status">Проверяем основания рекомендации…</p>}
    {error && <p role="alert">{error}</p>}
    {data && <>
      {data.quality_provenance === 'DEMONSTRATION_ONLY' && <p className="warning">{data.embedding_model?.provider === 'qwen-local-demo' ? 'Демонстрационная рекомендация с локальными Qwen-векторами. Промышленное качество не подтверждено.' : 'Демонстрационная рекомендация на синтетических данных. Промышленное качество не подтверждено.'}</p>}
      <p role="status"><strong>{data.status === 'RECOMMENDED' ? 'Есть обоснованное предложение' : data.status === 'ABSTAINED' ? 'Нет обоснованной рекомендации' : 'Рекомендация пока недоступна'}</strong><br />{data.reasoning_summary}</p>
      {data.recommended_value && <p className="compared-value">Предлагаемое текущее значение: <DataValue value={data.recommended_value.value} /> {data.recommended_value.unit}</p>}
      {data.confidence !== null && <p>Сила основания: <strong>{data.confidence} согласованных независимых групп прошлых случаев</strong>. Это количество оснований, а не вероятность правильного ответа.</p>}
      {data.evidence_summary.independent_groups !== undefined && data.confidence === null && <p>Независимых групп: {data.evidence_summary.independent_groups}. Для предложения требуется не менее {data.evidence_summary.minimum_groups}.</p>}
      <p className="muted">Авторитетный источник не задан. Правила, шаблон клиента и Forest Codex не настроены.</p>
      {data.status === 'RECOMMENDED' && <>
        <div className="comparison-grid">{currentValues.map(value => <div className="source-card" key={value.value_id}><h4>{value.source_name}</h4><DataValue value={value.value} /> {value.unit}{value.value_id === data.recommended_value_id && <p><strong>Предложено на основании истории</strong></p>}</div>)}</div>
        <button type="button" disabled={!canUse || disabled || !data.audit_reference} onClick={() => onUse(data)}>Использовать предложение в форме</button>
        {!canUse && <p className="muted">Чтобы использовать предложение, начните рассмотрение под ролью с правом принятия решений.</p>}
      </>}
      {!!data.conflicting_evidence.length && <p className="warning">История содержит разные исходы. Большинство не используется для выбора ответа.</p>}
      {data.evidence.map(item => <article className="source-card" key={item.decision_id}>
        <h4>{outcomeLabels.get(item.outcome) ?? item.outcome}</h4>
        <p>{item.context_summary.subject} · {item.context_summary.attribute_code}</p>
        <p><DataValue value={item.selected_value} /> {item.unit}</p>
        <p>{item.actor_display_name} · {new Date(item.decided_at).toLocaleString()}</p>
        <p className="human-reason">{item.reason}</p>
        {item.source_correspondence.map(mapping => <p key={mapping.historical_source_id}>Соответствие: {roleLabels.get(mapping.logical_role) ?? mapping.logical_role} → {currentValues.find(value => value.source_id === mapping.current_source_id)?.source_name ?? 'текущий источник'}.</p>)}
        <Identifier>Decision: {item.decision_id}</Identifier>
        {onOpenDecision && <button type="button" onClick={() => onOpenDecision(item.decision_id)}>Посмотреть основание решения</button>}
      </article>)}
      <details><summary>Ограничения и версии рекомендации</summary>
        <ul>{data.limitations.map(value => <li key={value}>{value}</li>)}</ul>
        <p>Политика: {data.recommendation_policy_version}. Соответствие источников: {data.source_mapping_version ?? 'не настроено'}.</p>
        <Identifier>Контекст: {data.context_fingerprint}</Identifier><br /><Identifier>Версия поиска: {data.retrieval_version ?? 'нет'}</Identifier>
        <p>Рассчитано: {new Date(data.generated_at).toLocaleString()}. Перед сохранением основания проверяются повторно.</p>
      </details>
    </>}
    <button type="button" disabled={disabled} onClick={() => { setData(null); setError(''); onInvalidated(); setAttempt(value => value + 1); }}>Обновить рекомендацию</button>
  </section>;
}
