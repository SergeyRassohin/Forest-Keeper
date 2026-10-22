import { useEffect, useState } from 'react';
import { StatusBadge, EmptyState, DataValue, Identifier } from './ui';
import { requestJson as api, SessionExpired, type User } from './api';

type Profile = { id: string; code: string; version: string; domain: string; synthetic: boolean };
type Analysis = { id: string; status: string; records_processed: number; created_at: string; mapping_snapshot: { domain: string } };
type Run = { id: string; status: string; records_processed: number; candidates_generated: number; status_counts: Record<string, number>; diagnostics: { coverage_limited?: boolean; records_without_candidates?: number; pairs_omitted_cap?: number; candidate_reduction_ratio?: string }; error_text: string | null; profile_hash: string; profile_snapshot: { code: string; version: string; engine_version: string }; based_on_previous_profile: boolean; input_analysis_ids: string[] };
type Candidate = { id: string; run_id: string; status: string; confidence: string; reason: string; raw_record_a_id: string; raw_record_b_id: string; confirmed_by: string | null };
type Signal = { attribute_code: string; algorithm: string; inputs: unknown[]; score: string | null; weight: string; weighted_contribution: string; tolerance: string; code: string };
type Detail = Candidate & { manual_review?: { actor_id: string; reviewed_at: string; reason: string; from_status: string; to_status: string } | null; run: Run; evidence: { signals: Signal[]; threshold_policy: string; threshold_decision: string; identity_rules_matched: number[]; negative_keys: string[]; blocking: unknown; input_context: unknown }; records: { raw_record_id: string; source: { name: string; code: string }; filename: string; file_hash: string; source_record_key: string | null; source_position: unknown; values: { attribute_code: string; raw_value: unknown; normalized_value: unknown; unit: string | null; quality_status: string }[] }[] };
const names = new Map<string, string>(Object.entries({ NEW: 'Принят', QUEUED: 'В очереди', PROCESSING: 'Сопоставление выполняется', COMPLETED: 'Сопоставление завершено', FAILED: 'Сопоставление прервано', MATCHED: 'Сопоставлено', POSSIBLE_MATCH: 'Требует проверки', NOT_MATCHED: 'Не сопоставлено' }));
const reasons: Record<string, string> = { EXPLICIT_UNIQUE_IDENTITY_RULE: 'Уникальный составной идентификатор совпал по явному правилу.', STRONG_KEY_DISAGREEMENT: 'Уникальные ключи различаются: похожесть названия не отменяет это различие.', NO_APPROVED_FUZZY_THRESHOLD: 'Для похожести не утверждён порог автоматического подтверждения.', AMBIGUOUS_IDENTITY: 'Идентификатор повторяется: единственная пара не определена.', CONFLICTING_STRONG_SIGNALS: 'Сильные признаки противоречат друг другу.' };

function useRemote<T>(path: string | null, expired: () => void, revision: number, repeat = true): { value?: T; error?: string } {
  const [state, setState] = useState<{ path: string | null; value?: T; error?: string }>({ path: null });
  useEffect(() => {
    if (!path) return;
    const url = path;
    const controller = new AbortController();
    let timer: number | undefined;
    async function load() {
      try {
        const value = await api<T>(url, { signal: controller.signal });
        if (!controller.signal.aborted) setState({ path: url, value });
      } catch (cause) {
        if (!controller.signal.aborted) {
          if (cause instanceof SessionExpired) expired();
          else setState((current) => ({ path: url, value: current.path === url ? current.value : undefined, error: 'Не удалось загрузить данные сопоставления.' }));
        }
      }
      if (repeat && !controller.signal.aborted) timer = window.setTimeout(() => { void load(); }, 2000);
    }
    void load();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [path, expired, revision, repeat]);
  return state.path === path ? state : {};
}

export function Matching({ user, onSessionExpired, onConflicts }: { user: User; onSessionExpired: () => void; onConflicts?: (id: string) => void }) {
  const [revision, setRevision] = useState(0);
  const [profileId, setProfileId] = useState('');
  const [a, setA] = useState('');
  const [b, setB] = useState('');
  const [runId, setRunId] = useState('');
  const [candidateId, setCandidateId] = useState('');
  const [filter, setFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [inputOffset, setInputOffset] = useState(0);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const profiles = useRemote<Profile[]>('/matching-profiles', onSessionExpired, revision, false);
  const inputs = useRemote<Analysis[]>(`/analysis?limit=50&offset=${inputOffset}`, onSessionExpired, revision, false);
  const history = useRemote<Run[]>(`/matching-runs?limit=10&offset=${historyOffset}`, onSessionExpired, revision);
  const run = useRemote<Run>(runId ? `/matching-runs/${runId}` : null, onSessionExpired, revision);
  const candidates = useRemote<Candidate[]>(runId ? `/matching-runs/${runId}/candidates?limit=50&offset=${offset}${filter ? '&status=' + filter : ''}` : null, onSessionExpired, revision);
  const detail = useRemote<Detail>(candidateId ? `/match-candidates/${candidateId}` : null, onSessionExpired, revision);
  const selectedProfile = profileId || profiles.value?.find((item) => item.code === 'synthetic-material')?.id || '';
  const completed = inputs.value?.filter((item) => item.status === 'COMPLETED') ?? [];
  function chooseRun(id: string) { setRunId(id); setCandidateId(''); setOffset(0); setReason(''); }
  async function mutate(path: string, body: unknown, started: boolean) {
    setBusy(true); setError('');
    try {
      const value = await api<Run | Candidate>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (started) { chooseRun(value.id); setHistoryOffset(0); }
      setReason(''); setRevision((current) => current + 1);
    } catch (cause) {
      if (cause instanceof SessionExpired) onSessionExpired();
      else setError(cause instanceof Error ? cause.message : 'Не удалось выполнить действие.');
    } finally { setBusy(false); }
  }
  const fetchError = [profiles, inputs, history, run, candidates, detail].find((item) => item.error)?.error;
  return <main className="shell" aria-label="Сопоставление">
    <p className="eyebrow">Идентичность записей</p><h1>Сопоставление</h1>
    <p>Сравнение определяет возможную идентичность записей. Оно не выбирает истинные значения и не объединяет исходные записи.</p>
    {(error || fetchError) && <p role="alert" className="warning">{error || fetchError}</p>}
    {user.permissions.includes('analysis.run') && <section className="panel matching-setup" aria-label="Новый запуск сопоставления">
      <h2>Сравнить два источника</h2>
      <label>Профиль сопоставления<select value={selectedProfile} onChange={(event) => setProfileId(event.target.value)}>{profiles.value?.map((profile) => <option key={profile.id} value={profile.id}>{profile.code} v{profile.version}{profile.synthetic ? ' — синтетический профиль' : ''}</option>)}</select></label>
      {(['A', 'B'] as const).map((side) => <label key={side}>Нормализация источника {side}<select value={side === 'A' ? a : b} onChange={(event) => { if (side === 'A') setA(event.target.value); else setB(event.target.value); }}><option value="">Выберите завершённый запуск</option>{[a,b].filter((id) => id && !completed.some((item) => item.id === id)).filter((id,index,array) => array.indexOf(id) === index).map((id) => <option key={id} value={id}>{id} · выбран на другой странице</option>)}{completed.map((item) => <option key={item.id} value={item.id}>{item.mapping_snapshot.domain} · {item.records_processed} записей · {item.id}</option>)}</select></label>)}
      <button disabled={!inputOffset} onClick={() => setInputOffset(Math.max(0, inputOffset - 50))}>Предыдущие входные запуски</button><button disabled={(inputs.value?.length ?? 0) < 50} onClick={() => setInputOffset(inputOffset + 50)}>Следующие входные запуски</button>
      <button className="primary" disabled={busy || !a || !b || a === b || !selectedProfile} onClick={() => void mutate('/matching-runs', { analysis_run_ids: [a,b], profile_id: selectedProfile }, true)}>Запустить сопоставление</button>
    </section>}
    <section className="panel" aria-label="История сопоставления"><h2>Запуски</h2>{!history.value && !fetchError && <p role="status">Загружаем историю сопоставления…</p>}
      <label>Запуск сопоставления<select value={runId} onChange={(event) => chooseRun(event.target.value)}><option value="">Выберите запуск</option>{runId && !history.value?.some((item) => item.id === runId) && <option value={runId}>{runId}</option>}{history.value?.map((item) => <option key={item.id} value={item.id}>{item.id} · {(names.get(item.status) ?? item.status)}</option>)}</select></label>
      <button disabled={!historyOffset} onClick={() => { chooseRun(''); setHistoryOffset(Math.max(0, historyOffset - 10)); }}>Предыдущие сопоставления</button><button disabled={(history.value?.length ?? 0) < 10} onClick={() => { chooseRun(''); setHistoryOffset(historyOffset + 10); }}>Следующие сопоставления</button>
    </section>
    {history.value?.length === 0 && <EmptyState title="Сопоставлений пока нет">Завершите нормализацию двух источников и выберите их для сравнения.</EmptyState>}
    {run.value && <section className="panel" aria-label="Результат сопоставления">
      {run.value.status === 'COMPLETED' && onConflicts && user.permissions.includes('conflict.view') && <button onClick={() => onConflicts(run.value!.id)}>Открыть конфликты сопоставления</button>}
      <p role="status"><StatusBadge value={run.value.status} label={names.get(run.value.status)} /> · записей {run.value.records_processed}, кандидатов {run.value.candidates_generated}</p>
      {run.value.status !== 'COMPLETED' && <p className="warning">Результаты частичные до успешного завершения.</p>}
      {run.value.error_text && <p role="alert">{run.value.error_text}. Для повтора создайте новый запуск; история сохранена.</p>}
      {run.value.based_on_previous_profile && <p className="warning">Результат рассчитан по предыдущей версии профиля. Критерии изменились; для новой оценки нужен отдельный запуск.</p>}
      <p>Профиль {run.value.profile_snapshot.code} v{run.value.profile_snapshot.version} · движок {run.value.profile_snapshot.engine_version}</p>
      <details><summary>Контрольная сумма профиля</summary><Identifier>SHA-256 профиля: {run.value.profile_hash}</Identifier></details>
      <p>Forest Codex — эталон клиента — пока не настроен. Порог автоматического подтверждения похожих записей не утверждён.</p>
      <p>Совпадение: {run.value.status_counts.MATCHED ?? 0} · Требует проверки: {run.value.status_counts.POSSIBLE_MATCH ?? 0} · Разные сущности: {run.value.status_counts.NOT_MATCHED ?? 0}</p>
      {run.value.diagnostics.coverage_limited && <p className="warning">Охват ограничен размером групп или числом кандидатов. Пропущенные пары не объявлены разными сущностями.</p>}
      <p>Без кандидатов: {run.value.diagnostics.records_without_candidates ?? 0}. Это не доказательство отсутствия совпадения.</p>
      <label>Статус кандидата<select value={filter} onChange={(event) => { setFilter(event.target.value); setOffset(0); setCandidateId(''); }}><option value="">Все</option>{['MATCHED','POSSIBLE_MATCH','NOT_MATCHED'].map((status) => <option key={status} value={status}>{(names.get(status) ?? status)}</option>)}</select></label>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Таблица значений"><table><thead><tr><th>Пара исходных записей</th><th>Статус</th><th>Оценка</th><th>Основание</th></tr></thead><tbody>{candidates.value?.map((candidate) => <tr key={candidate.id}><td><button aria-label={'Сравнить записи ' + candidate.raw_record_a_id + ' ↔ ' + candidate.raw_record_b_id} onClick={() => { setCandidateId(candidate.id); setReason(''); }}>Сравнить записи</button><br /><Identifier>{candidate.raw_record_a_id.slice(0, 8)} ↔ {candidate.raw_record_b_id.slice(0, 8)}</Identifier></td><td><StatusBadge value={candidate.status} label={names.get(candidate.status)} /></td><td>{candidate.confidence}</td><td>{candidate.confirmed_by ? "Подтверждено человеком; обоснование в карточке." : reasons[candidate.reason] ?? candidate.reason}</td></tr>)}</tbody></table></div>
      <button disabled={!offset} onClick={() => { setOffset(Math.max(0, offset - 50)); setCandidateId(''); }}>Предыдущие кандидаты</button><button disabled={(candidates.value?.length ?? 0) < 50} onClick={() => { setOffset(offset + 50); setCandidateId(''); }}>Следующие кандидаты</button>
    </section>}
    {detail.value && <section className="panel" aria-label="Основание сопоставления"><h2>{(names.get(detail.value.status) ?? detail.value.status)} · {detail.value.confidence}</h2>
      {detail.value.manual_review && <section aria-label="Решение человека"><h3>Обоснование проверки совпадения</h3><p>Подтверждена только идентичность записей. Значения атрибутов этим действием не выбираются.</p><p>{detail.value.manual_review.reason}</p><p>Пользователь: {detail.value.manual_review.actor_id} · {new Date(detail.value.manual_review.reviewed_at).toLocaleString()} · {(names.get(detail.value.manual_review.from_status) ?? detail.value.manual_review.from_status)} → {(names.get(detail.value.manual_review.to_status) ?? detail.value.manual_review.to_status)}</p></section>}
      <p>Первоначальное основание алгоритма: {reasons[detail.value.reason] ?? detail.value.reason}</p>
      <div className="comparison-grid">{detail.value.records.map((record) => <section className="source-card" key={record.raw_record_id} aria-label={'Сравниваемая запись ' + record.raw_record_id}><h3>{record.source.name} · {record.filename} · {record.source_record_key ?? 'без ключа'}</h3><p>{record.source.code} · {record.raw_record_id}</p><pre>Позиция: {JSON.stringify(record.source_position)}</pre><p className="checksum">SHA-256 оригинала: {record.file_hash}</p><div className="table-scroll" tabIndex={0} role="region" aria-label="Таблица значений"><table><thead><tr><th>Атрибут</th><th>Исходное</th><th>Нормализованное</th><th>Единица</th><th>Качество</th></tr></thead><tbody>{record.values.map((value) => <tr key={value.attribute_code}><td>{value.attribute_code}</td><td><DataValue value={value.raw_value} /></td><td><DataValue value={value.normalized_value} /></td><td>{value.unit ?? '—'}</td><td><StatusBadge value={value.quality_status} /></td></tr>)}</tbody></table></div></section>)}</div>
      <h3>Сигналы и вклад в оценку</h3><div className="table-scroll" tabIndex={0} role="region" aria-label="Таблица значений"><table><thead><tr><th>Атрибут / алгоритм</th><th>Значения</th><th>Сходство</th><th>Вес / вклад</th><th>Допуск / пояснение</th></tr></thead><tbody>{detail.value.evidence.signals.map((signal) => <tr key={signal.attribute_code}><td>{signal.attribute_code} / {signal.algorithm}</td><td>{signal.inputs.map((value, index) => <div key={index}><DataValue value={value} /></div>)}</td><td>{signal.score ?? 'UNKNOWN'}</td><td>{signal.weight} / {signal.weighted_contribution}</td><td>{signal.tolerance} / {signal.code}</td></tr>)}</tbody></table></div>
      <p>Правило порогов: {detail.value.evidence.threshold_policy} · решение: {detail.value.evidence.threshold_decision}. Оценка 1 сама по себе не подтверждает пару.</p>
      <details><summary>Контекст и генерация кандидата</summary><pre>{JSON.stringify({ blocking: detail.value.evidence.blocking, context: detail.value.evidence.input_context }, null, 2)}</pre></details>
      {user.permissions.includes('match.review') && detail.value.status === 'POSSIBLE_MATCH' && detail.value.run.status === 'COMPLETED' && <form onSubmit={(event) => event.preventDefault()}><label>Причина подтверждения или отклонения<textarea value={reason} maxLength={1000} onChange={(event) => setReason(event.target.value)} /></label><button disabled={busy || !reason.trim()} onClick={() => void mutate(`/match-candidates/${candidateId}/review`, { status: 'MATCHED', reason }, false)}>Подтвердить совпадение</button><button disabled={busy || !reason.trim()} onClick={() => void mutate(`/match-candidates/${candidateId}/review`, { status: 'NOT_MATCHED', reason }, false)}>Отклонить совпадение</button></form>}
      {detail.value.confirmed_by && <p>Подтвердил пользователь: {detail.value.confirmed_by}</p>}
    </section>}
  </main>;
}
