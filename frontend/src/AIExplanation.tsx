import { useEffect, useRef, useState } from 'react';
import { requestJson, SessionExpired } from './api';
import { Identifier } from './ui';

type Props = { conflictId: string; contextVersion: string; disabled?: boolean;
  onSessionExpired: () => void; onOpenDecision?: (id: string) => void };
type Clause = { code: string; text: string; decision_ids: string[] };
type Model = { model_id: string; revision: string; prompt_version: string;
  quality_provenance: 'LOCAL_QWEN_DEMO'; production_accepted: false };
type View = { request_id: string; state: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  reason_code?: string | null; clauses?: Clause[]; model?: Model; context_fingerprint?: string };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const codes = new Set(['CURRENT_CONTEXT', 'SUPPORT', 'CONTRADICTION', 'ABSTENTION', 'LIMITATION']);
function object(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}
function readView(value: unknown, handle: string): View {
  if (!object(value) || value.request_id !== handle ||
    !['QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED'].includes(String(value.state))) throw new Error('Invalid AI status');
  if (value.state === 'COMPLETED') {
    if (!Array.isArray(value.clauses) || value.clauses.length !== 3 || !value.clauses.every(item =>
      object(item) && codes.has(String(item.code)) && typeof item.text === 'string' && item.text.length <= 8192 &&
      Array.isArray(item.decision_ids) && item.decision_ids.length <= 1 && item.decision_ids.every(id => typeof id === 'string' && uuid.test(id))) ||
      !object(value.model) || typeof value.model.model_id !== 'string' || value.model.model_id.length > 128 ||
      typeof value.model.revision !== 'string' || !/^[0-9a-f]{40}$/.test(value.model.revision) ||
      typeof value.model.prompt_version !== 'string' || value.model.prompt_version.length > 128 ||
      typeof value.context_fingerprint !== 'string' || !/^[0-9a-f]{64}$/.test(value.context_fingerprint) ||
      value.model.quality_provenance !== 'LOCAL_QWEN_DEMO' || value.model.production_accepted !== false)
      throw new Error('Invalid AI explanation');
    if (new Set(value.clauses.map(item => item.code)).size !== 3) throw new Error('Invalid AI clauses');
  }
  return value as unknown as View;
}

export function AIExplanation(props: Props) {
  return <ExplanationJob key={props.conflictId + ':' + props.contextVersion} {...props} />;
}

function ExplanationJob({ conflictId, disabled = false, onSessionExpired, onOpenDecision }: Props) {
  const [handle, setHandle] = useState<string | null>(null);
  const [data, setData] = useState<View | null>(null);
  const [error, setError] = useState('');
  const [requesting, setRequesting] = useState(false);
  const [polling, setPolling] = useState(false);
  const [pollAttempt, setPollAttempt] = useState(0);
  const retryRequest = useRef<string | null>(null);
  const requestController = useRef<AbortController | null>(null);
  const pollController = useRef<AbortController | null>(null);
  useEffect(() => () => {
    requestController.current?.abort(); pollController.current?.abort();
  }, []);
  useEffect(() => {
    if (!handle || !polling) return;
    const controller = new AbortController(); pollController.current = controller;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const started = Date.now();
    async function check() {
      try {
        const value = readView(await requestJson<unknown>(`/conflicts/${conflictId}/ai-explanations/${handle}`, { signal: controller.signal }), handle!);
        if (controller.signal.aborted) return;
        setData(value); setError('');
        if (value.state === 'COMPLETED' || value.state === 'FAILED') setPolling(false);
        else if (Date.now() - started >= 480_000) {
          setPolling(false); setError('Объяснение ещё не готово. Можно проверить состояние позже.');
        } else timer = setTimeout(() => { void check(); }, 2500);
      } catch (cause) {
        if (controller.signal.aborted) return;
        setPolling(false);
        if (cause instanceof SessionExpired) onSessionExpired();
        else setError('Не удалось получить AI-объяснение. Ручное рассмотрение остаётся доступно.');
      }
    }
    void check();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [conflictId, handle, polling, pollAttempt, onSessionExpired]);
  async function start() {
    const controller = new AbortController(); requestController.current?.abort(); requestController.current = controller;
    const requestId = retryRequest.current ?? crypto.randomUUID(); retryRequest.current = requestId;
    setRequesting(true); setError(''); setData(null); setHandle(null); setPolling(false);
    try {
      const accepted = await requestJson<{ request_id: string }>(`/conflicts/${conflictId}/ai-explanation`, {
        method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: requestId, language: 'ru' }),
      });
      if (controller.signal.aborted) return;
      if (!accepted || typeof accepted.request_id !== 'string' || !uuid.test(accepted.request_id)) throw new Error('Invalid AI request');
      retryRequest.current = null; setHandle(accepted.request_id);
      setData({ request_id: accepted.request_id, state: 'QUEUED' }); setPolling(true);
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof SessionExpired) onSessionExpired();
      else setError('AI-объяснение сейчас недоступно или очередь занята. Вы можете продолжить рассмотрение самостоятельно.');
    } finally { if (!controller.signal.aborted) setRequesting(false); }
  }
  async function cancel() {
    if (!handle) return;
    pollController.current?.abort(); setPolling(false); setError(''); setRequesting(true);
    const controller = new AbortController(); requestController.current = controller;
    try {
      const value = readView(await requestJson<unknown>(`/conflicts/${conflictId}/ai-explanations/${handle}/cancel`, { method: 'POST', signal: controller.signal }), handle);
      if (!controller.signal.aborted) setData(value);
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof SessionExpired) onSessionExpired();
      else setError('Не удалось подтвердить отмену ожидания. Можно проверить состояние запроса.');
    } finally { if (!controller.signal.aborted) setRequesting(false); }
  }
  const terminal = data?.state === 'COMPLETED' || data?.state === 'FAILED';
  return <section className="precedent-panel" aria-label="Локальное AI-объяснение">
    <h3>Локальное AI-объяснение</h3>
    <p className="human-boundary">Объяснение составляется по отдельному запросу из проверенных фактов. AI не выбирает истинное значение и не сохраняет решение за вас.</p>
    {error && <p role="alert">{error}</p>}
    {data?.state === 'QUEUED' && polling && <p role="status">Запрос принят. Ожидаем объяснение…</p>}
    {data?.state === 'PROCESSING' && polling && <p role="status">Локальная модель готовит объяснение… Форму можно продолжать заполнять.</p>}
    {data?.state === 'FAILED' && <p role="status">{data.reason_code === 'AI_CONTEXT_STALE' ? 'Основания изменились. Запросите объяснение для текущего контекста.' : data.reason_code === 'AI_CANCELLED' ? 'Ожидание отменено. Ручное рассмотрение доступно.' : 'Обоснованное AI-объяснение недоступно. Используйте проверенные факты и ручное рассмотрение.'}</p>}
    {data?.state === 'COMPLETED' && <>
      <p className="warning">Демонстрационный режим локальной Qwen. Промышленное качество не подтверждено.</p>
      <ol>{data.clauses?.map(clause => <li key={clause.code}><p>{clause.text}</p>{clause.decision_ids.map(id => <span key={id}>{onOpenDecision ? <button type="button" onClick={() => onOpenDecision(id)}>Посмотреть подтверждённое решение</button> : <Identifier>{id}</Identifier>}</span>)}</li>)}</ol>
      <details><summary>Версия модели и основания</summary><p>Модель: <Identifier>{data.model?.model_id}</Identifier></p><p>Revision: <Identifier>{data.model?.revision}</Identifier>. Формат объяснения: {data.model?.prompt_version}.</p><p>Контекст: <Identifier>{data.context_fingerprint}</Identifier></p></details>
    </>}
    <button type="button" disabled={disabled || requesting || (!!handle && !terminal)} onClick={() => void start()}>{requesting ? 'Отправляем запрос…' : data?.state === 'COMPLETED' ? 'Обновить AI-объяснение' : 'Получить AI-объяснение'}</button>
    {handle && !terminal && !polling && !requesting && <button type="button" onClick={() => { setError(''); setPollAttempt(value => value + 1); setPolling(true); }}>Проверить состояние</button>}
    {handle && !terminal && <button type="button" disabled={requesting} onClick={() => void cancel()}>Отменить ожидание</button>}
  </section>;
}
