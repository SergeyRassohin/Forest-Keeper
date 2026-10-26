import { useCallback, useEffect, useRef, useState } from 'react';
import { requestJson as api, SessionExpired } from './api';
import { type Receipt, type ReviewContext, type Decision, outcomeLabels } from './decisionTypes';
import { DecisionCard } from './Decisions';
import { Recommendation } from './Recommendation';
import { AIExplanation } from './AIExplanation';
import type { RecommendationResult } from './recommendationTypes';
import { DataValue, Identifier, StatusBadge } from './ui';

type Submission = { context_version: string; idempotency_key: string; decision_type: string;
  selected_source_id?: string; selected_value_id?: string; recommendation_reference?: string; corrected_value?: string;
  corrected_unit?: string | null; reason: string; confirmed: true; supersedes_decision_id: string | null };

export function HumanReview({ conflictId, onSessionExpired, onSaved, onOpenDecision, showRecommendations = false, canAcceptRecommendation = false }: {
  conflictId: string; onSessionExpired: () => void; onSaved: () => void; onOpenDecision?: (id: string) => void; showRecommendations?: boolean; canAcceptRecommendation?: boolean;
}) {
  const [context, setContext] = useState<ReviewContext | null>(null);
  const [history, setHistory] = useState<Decision[]>([]);
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState(false);
  const [choice, setChoice] = useState('');
  const [value, setValue] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirm, setConfirm] = useState(false);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [pending, setPending] = useState<Submission | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const confirmedSubmission = useRef<Submission | null>(null);
  const confirmButton = useRef<HTMLButtonElement>(null);
  const [retryLoad, setRetryLoad] = useState(0);
  const [appliedRecommendation, setAppliedRecommendation] = useState<RecommendationResult | null>(null);
  const invalidateRecommendation = useCallback(() => setAppliedRecommendation(null), []);
  const changedContext = useCallback(() => { setAppliedRecommendation(null); setEditing(false); setChoice(''); setReason(''); setRetryLoad(value => value + 1); }, []);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const review = await api<ReviewContext>(`/conflicts/${conflictId}/review-context`, { signal: controller.signal });
        if (!controller.signal.aborted) setContext(review);
      } catch (cause) {
        if (!controller.signal.aborted) {
          if (cause instanceof SessionExpired) onSessionExpired();
          else { setError(cause instanceof Error ? cause.message : 'Не удалось загрузить контекст рассмотрения.'); setContext(null); }
        }
      }
    }
    void load();
    return () => controller.abort();
  }, [conflictId, retryLoad, onSessionExpired]);
  useEffect(() => {
    const controller = new AbortController();
    api<Decision[]>(`/conflicts/${conflictId}/decisions?limit=50&offset=${offset}`, { signal: controller.signal })
      .then((items) => { if (!controller.signal.aborted) setHistory(items); })
      .catch((cause) => { if (!controller.signal.aborted) { if (cause instanceof SessionExpired) onSessionExpired(); else setError(cause instanceof Error ? cause.message : 'Не удалось загрузить историю.'); } });
    return () => controller.abort();
    // History navigation must never silently refresh the evidence token of an edited decision.
  }, [conflictId, offset, retryLoad, onSessionExpired]);
  useEffect(() => {
    if (confirm) { dialog.current?.showModal(); confirmButton.current?.focus(); }
    else if (dialog.current?.open) dialog.current.close();
  }, [confirm]);
  async function startReview() {
    if (!context) return;
    setBusy(true); setError(''); setReceipt(null);
    try {
      const review = await api<ReviewContext>(`/conflicts/${conflictId}/review`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ context_version: context.context_version, supersedes_decision_id: context.current_decision?.id ?? null }) });
      setAppliedRecommendation(null); setContext(review); setEditing(true); setChoice(''); setValue(''); setReason(''); setPending(null); onSaved();
    } catch (cause) { handleError(cause); setRetryLoad((number) => number + 1); }
    finally { setBusy(false); }
  }
  function handleError(cause: unknown) {
    if (cause instanceof SessionExpired) onSessionExpired();
    else setError(cause instanceof Error ? cause.message : 'Сохранение не подтверждено.');
  }
  const selected = context?.selectable_values.find((item) => 'SOURCE:' + item.value_id === choice);
  const outcome = selected ? 'SELECT_VALUE' : choice;
  function submission(): Submission | null {
    if (!context || !reason.trim() || !choice || !context.allowed_actions.includes(outcome)) return null;
    return { context_version: context.context_version, idempotency_key: crypto.randomUUID(),
      decision_type: outcome, reason, confirmed: true, supersedes_decision_id: context.current_decision?.id ?? null,
      ...(selected ? { selected_source_id: selected.source_id, selected_value_id: selected.value_id } : {}),
      ...(appliedRecommendation?.audit_reference && appliedRecommendation.review_context_version === context.context_version && selected?.value_id === appliedRecommendation.recommended_value_id ? { recommendation_reference: appliedRecommendation.audit_reference } : {}),
      ...(outcome === 'ENTER_VALUE' ? { corrected_value: value, corrected_unit: context.correction_policy.unit } : {}) };
  }
  async function send(body: Submission) {
    setBusy(true); setError(''); setPending(body);
    try {
      const result = await api<Receipt>(`/conflicts/${conflictId}/decisions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      setAppliedRecommendation(null); setReceipt(result); setPending(null); setEditing(false); setConfirm(false); setChoice(''); setReason('');
      setRetryLoad((number) => number + 1); onSaved();
    } catch (cause) {
      handleError(cause); setConfirm(false);
      // An unknown response may follow a successful commit. Keep the exact key and payload for retry.
      if (cause && typeof cause === 'object' && 'status' in cause && Number(cause.status) < 500) {
        setPending(null);
        if (Number(cause.status) !== 422) { setEditing(false); setChoice(''); setRetryLoad((number) => number + 1); }
      }
    } finally { setBusy(false); }
  }
  const canConfirm = !!choice && !!reason.trim() && (outcome !== 'ENTER_VALUE' || !!value.trim());
  return <section className="panel human-review" aria-label="Рассмотрение конфликта">
    <p className="eyebrow">Контролируемое решение человека</p><h2>Рассмотрение конфликта</h2>
    <p>Проверьте значения, происхождение и Basis выше. Решение сохраняется только внутри Forest Keeper; исходные системы не изменяются.</p>
    {error && <p role="alert" tabIndex={-1}>{error}</p>}
    {!context && !error && <p role="status">Загружаем контекст рассмотрения…</p>}
    {receipt && <div className="decision-receipt" role="status"><h3>Решение сохранено</h3><p>{receipt.message}</p><p>Decision ID: <Identifier>{receipt.decision_id}</Identifier></p><StatusBadge value={receipt.conflict_status} /><DecisionCard decision={receipt.decision} title="Подтверждение сохранённого решения" />{onOpenDecision && <button onClick={() => onOpenDecision(receipt.decision_id)}>Открыть решение в реестре</button>}</div>}
    {pending && !busy && <div className="warning"><p>Ответ о сохранении не получен. Повторная отправка с тем же ключом вернёт сохранённое решение и не создаст дубль.</p><button onClick={() => void send(pending)}>Повторить сохранение</button></div>}
    {context && <>
      {showRecommendations && <Recommendation key={context.context_version} conflictId={conflictId} contextVersion={context.context_version} currentValues={context.selectable_values} canUse={editing && canAcceptRecommendation && context.allowed_actions.includes('SELECT_VALUE')} disabled={busy || !!pending} onInvalidated={invalidateRecommendation} onContextChanged={changedContext} onSessionExpired={onSessionExpired} onOpenDecision={onOpenDecision} onUse={(result) => {
        const selected = context.selectable_values.find(value => value.value_id === result.recommended_value_id && value.source_id === result.recommended_source_id);
        if (selected && result.audit_reference && result.review_context_version === context.context_version && editing && canAcceptRecommendation) { setChoice('SOURCE:' + selected.value_id); setAppliedRecommendation(result); }
      }} />}
      {showRecommendations && <AIExplanation conflictId={conflictId} contextVersion={context.context_version} disabled={busy || !!pending} onSessionExpired={onSessionExpired} onOpenDecision={onOpenDecision} />}
      {context.current_decision && <DecisionCard decision={context.current_decision} title="Действующее решение по этому конфликту" />}
      {context.can_start_review && !editing && !pending && <button className="primary" disabled={busy} onClick={() => void startReview()}>{context.current_decision ? context.conflict_status === 'IN_REVIEW' ? 'Продолжить рассмотрение' : 'Пересмотреть решение' : 'Начать рассмотрение'}</button>}
      {!context.can_start_review && <p className="muted">Режим просмотра. Для сохранения решения нужны бизнес-права и доступ к области данных.</p>}
      {context.known_unknowns.length > 0 && <p className="warning">В контексте есть отсутствующие, неизвестные или некорректные значения. Они не предлагаются как подтверждённое значение.</p>}
      {appliedRecommendation && <p className="notice">Предложение перенесено в форму. Укажите своё обоснование и подтвердите решение; выбор можно изменить.</p>}
      {editing && <form onSubmit={(event) => { event.preventDefault(); if (canConfirm && !pending && !busy) { confirmedSubmission.current = submission(); setConfirm(true); } }}>
        <fieldset disabled={busy || !!pending}><legend>Результат рассмотрения</legend>
          {context.allowed_actions.includes('SELECT_VALUE') && context.selectable_values.map((item) => <label className="role-choice" key={item.value_id}><input type="radio" name={'outcome-' + conflictId} value={'SOURCE:' + item.value_id} checked={choice === 'SOURCE:' + item.value_id} onChange={() => { setAppliedRecommendation(null); setChoice('SOURCE:' + item.value_id); }} />Источник {item.side}: {item.source_name} · {item.value} {item.unit}</label>)}
          {['ENTER_VALUE', 'INSUFFICIENT_DATA', 'DEFERRED'].filter((action) => context.allowed_actions.includes(action)).map((action) => <label className="role-choice" key={action}><input type="radio" name={'outcome-' + conflictId} value={action} checked={choice === action} onChange={() => { setAppliedRecommendation(null); setChoice(action); }} />{action === 'ENTER_VALUE' ? 'Указать другое значение' : outcomeLabels.get(action)}</label>)}
        </fieldset>
        {outcome === 'ENTER_VALUE' && <label>Подтверждённое значение{context.correction_policy.unit ? ' (' + context.correction_policy.unit + ')' : ''}<input value={value} maxLength={context.correction_policy.max_length} disabled={busy || !!pending} onChange={(event) => setValue(event.target.value)} required /><span className="muted">{context.correction_policy.kind === 'date' ? 'Дата в формате ГГГГ-ММ-ДД.' : 'Введите каноническое значение. Исходные записи сохранятся без изменений.'}</span></label>}
        <label><span id={'review-reason-' + conflictId}>Обоснование решения</span><textarea aria-labelledby={'review-reason-' + conflictId} required maxLength={2000} value={reason} disabled={busy || !!pending} onChange={(event) => setReason(event.target.value)} /></label>
        <p className="muted">Версия evidence: <Identifier>{context.evidence_hash}</Identifier></p>
        <button className="primary" disabled={busy || !!pending || !canConfirm}>Проверить перед сохранением</button>
      </form>}
      {context.history_count > 0 && <section aria-label="История рассмотрения"><h3>История решений</h3><ol className="decision-timeline">{history.map((item) => <li key={item.id}><StatusBadge value={item.status} label={item.status === 'ACTIVE' ? 'Действует' : 'Заменено'} /><p>{outcomeLabels.get(item.decision_type)} · {new Date(item.decided_at).toLocaleString()}</p><p className="human-reason">{item.reason}</p><p>{item.actor_display_name} · <Identifier>{item.user_id}</Identifier></p>{item.supersedes_decision_id && <p>Заменяет: <Identifier>{item.supersedes_decision_id}</Identifier></p>}{item.superseded_by && <p>Заменено: <Identifier>{item.superseded_by}</Identifier></p>}{onOpenDecision && <button onClick={() => onOpenDecision(item.id)}>Открыть решение {item.id.slice(0, 8)}</button>}<Identifier>{item.id}</Identifier></li>)}</ol><button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Предыдущая история рассмотрения</button><button disabled={history.length < 50} onClick={() => setOffset(offset + 50)}>Следующая история рассмотрения</button></section>}
    </>}
    <dialog ref={dialog} aria-labelledby="decision-confirm-title" onCancel={(event) => { if (busy) event.preventDefault(); else setConfirm(false); }}>
      <h2 id="decision-confirm-title">Подтвердите сохранение решения</h2>
      <p>{outcomeLabels.get(outcome)}</p><DataValue value={selected ? selected.value : outcome === 'ENTER_VALUE' ? value : null} /> {selected?.unit ?? context?.correction_policy.unit}
      <p className="human-reason">{reason}</p><p>Conflict: <Identifier>{conflictId}</Identifier></p>
      <p>Версия рассмотрения: <Identifier>{context?.context_version}</Identifier></p>
      <p className="human-boundary">Решение будет сохранено внутри Forest Keeper. Записи в 1С, ERP и файлах не изменятся.</p>
      <button disabled={busy} onClick={() => setConfirm(false)}>Вернуться к проверке</button>
      <button ref={confirmButton} className="primary" disabled={busy} onClick={() => { const body = confirmedSubmission.current; if (body && !busy) void send(body); }}>{busy ? 'Сохраняем…' : 'Сохранить решение'}</button>
    </dialog>
  </section>;
}
