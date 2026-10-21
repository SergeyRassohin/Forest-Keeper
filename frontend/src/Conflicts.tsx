import { useEffect, useState } from 'react';
import { requestJson as api, SessionExpired, type User } from './api';

type Run = { id: string; status: string; matching_run_id: string; records_processed: number; conflicts_generated: number; error_text: string | null };
type Row = { id: string; entity_id: string; matching_run_id: string; attribute_code: string; conflict_type: string; severity: string; status: string; detected_at: string; sources?: { source_name: string; source_record_key: string }[] };
type Value = { source_name: string; source_id: string; source_record_key: string; raw_record_id: string; entity_id: string; filename: string; file_hash: string; source_position: unknown; presence: string; value: { raw_value: unknown; raw_value_omitted: boolean; normalized_value: unknown; unit: string | null; quality_status: string; normalization_rule: unknown } | null };
type Detail = Row & { match_candidate_id: string; values_snapshot: Value[]; normalization_origins: { analysis_id: string; source_id: string; profile_id: string; profile_version: string; mapping_hash: string; engine_version: string }[]; basis: { reason_code: string; engine_version: string; config_hash: string; matching_profile_hash: string; matching_evidence: unknown; normalization_context: unknown }; based_on_previous_profile: boolean };

export function Conflicts({ user, onSessionExpired, initialRunId = '' }: { user: User; onSessionExpired: () => void; initialRunId?: string }) {
  const [matching, setMatching] = useState(initialRunId);
  const [matchingRuns, setMatchingRuns] = useState<{ id: string; status: string }[]>([]);
  const [rows, setRows] = useState<Row[]>([]);
  const [detailId, setDetailId] = useState('');
  const [detail, setDetail] = useState<Detail | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [filter, setFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let timer: number;
    async function load() {
      try {
        const query = `?limit=50&offset=${offset}${filter ? '&conflict_type=' + filter : ''}${matching ? '&matching_run_id=' + matching : ''}`;
        const [items, history, inputs, card] = await Promise.all([
          api<Row[]>('/conflicts' + query, { signal: controller.signal }),
          api<Run[]>('/conflict-runs?limit=50', { signal: controller.signal }),
          api<{ id: string; status: string }[]>('/matching-runs?limit=100', { signal: controller.signal }),
          detailId ? api<Detail>('/conflicts/' + detailId, { signal: controller.signal }) : Promise.resolve(null),
        ]);
        if (!controller.signal.aborted) { setRows(items); setRuns(history); setMatchingRuns(inputs); setDetail(card); setError(''); }
      } catch (cause) {
        if (!controller.signal.aborted) {
          if (cause instanceof SessionExpired) onSessionExpired();
          else setError(cause instanceof Error ? cause.message : 'Не удалось загрузить конфликты.');
        }
      }
      if (!controller.signal.aborted) timer = window.setTimeout(() => { void load(); }, 2000);
    }
    void load();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [matching, filter, offset, revision, detailId, onSessionExpired]);
  async function start() {
    setBusy(true); setError('');
    try {
      await api('/conflict-runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ matching_run_id: matching }) });
      setRevision((value) => value + 1);
    } catch (cause) {
      if (cause instanceof SessionExpired) onSessionExpired();
      else setError(cause instanceof Error ? cause.message : 'Не удалось запустить анализ.');
    } finally { setBusy(false); }
  }
  return <main className="shell" aria-label="Конфликты">
    <h1>Конфликты</h1>
    <p>Расхождения в подтверждённых парах. Нормализованное значение не является истиной.</p>
    <p>Решение человека ещё не принято</p>
    {error && <p role="alert" className="warning">{error}</p>}
    <label>Сопоставление для конфликтов<select value={matching} onChange={(event) => { setMatching(event.target.value); setOffset(0); setDetailId(''); setDetail(null); }}><option value="">Все сопоставления</option>{matching && !matchingRuns.some((item) => item.id === matching) && <option value={matching}>{matching}</option>}{matchingRuns.filter((item) => item.status === 'COMPLETED').map((item) => <option key={item.id}>{item.id}</option>)}</select></label>
    {user.permissions.includes('analysis.run') && <button disabled={!matching || busy} onClick={() => void start()}>Проверить конфликты</button>}
    {runs.filter((item) => !matching || item.matching_run_id === matching).map((item) => <p role="status" key={item.id}>Анализ {item.id}: {item.status} · пар {item.records_processed} · конфликтов в запуске (включая ранее сохранённые) {item.conflicts_generated}{item.error_text && ` · ${item.error_text}`}</p>)}
    <label>Тип конфликта<select value={filter} onChange={(event) => { setFilter(event.target.value); setOffset(0); }}><option value="">Все типы</option>{['VALUE_MISMATCH','MISSING','DUPLICATE','RULE_VIOLATION','ANOMALY'].map((kind) => <option key={kind}>{kind}</option>)}</select></label>
    <p>LOW — нейтральная техническая оценка; бизнес-политика важности пока не настроена.</p>
    <table><thead><tr>{['Конфликт','Сущность','Атрибут','Тип','Важность','Статус','Обнаружен'].map((label) => <th key={label}>{label}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td><button onClick={() => { setDetail(null); setDetailId(row.id); }}>{row.id}</button></td><td>{row.entity_id}<br />{row.sources?.map((item) => `${item.source_name}: ${item.source_record_key}`).join(' ↔ ')}</td><td>{row.attribute_code}</td><td>{row.conflict_type}</td><td>{row.severity}</td><td>{row.status}</td><td>{new Date(row.detected_at).toLocaleString()}</td></tr>)}</tbody></table>
    {!rows.length && <p>Конфликты не найдены. Проверьте состояние анализа.</p>}
    <button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Предыдущие конфликты</button><button disabled={rows.length < 50} onClick={() => setOffset(offset + 50)}>Следующие конфликты</button>
    {detail && <section className="panel" aria-label="Карточка конфликта"><h2>{detail.conflict_type} · {detail.attribute_code}</h2><p>Conflict ID: {detail.id}</p><p>Решение человека ещё не принято</p>
      {detail.based_on_previous_profile && <p className="warning">Результат по предыдущей версии профиля. Для новой оценки запустите анализ заново.</p>}
      <p>{detail.basis.reason_code === 'NORMALIZED_VALUES_DIFFER' ? 'Нормализованные значения одного атрибута различаются.' : detail.basis.reason_code === 'SOURCE_VALUE_ABSENT' ? 'Значение отсутствует в одном источнике; причина указана для каждой стороны.' : 'Несколько записей одного источника подтверждены как одна сущность.'}</p>
      {detail.values_snapshot.map((item) => <article key={item.raw_record_id}><h3>{item.source_name} · {item.source_record_key}</h3><p>Источник: {item.source_id} · Запись: {item.raw_record_id}</p><p>Файл: {item.filename} · SHA-256: {item.file_hash}</p><p>Позиция: {JSON.stringify(item.source_position)}</p><p>Наличие: {item.presence} · Качество: {item.value?.quality_status ?? 'Не отображено схемой'}</p><p>Исходное: {JSON.stringify(item.value?.raw_value)}{item.value?.raw_value_omitted && ' (полное значение сохранено в исходной записи)'}</p><p>Нормализованное: {JSON.stringify(item.value?.normalized_value)} {item.value?.unit}</p><details><summary>Нормализация</summary><pre>{JSON.stringify(item.value?.normalization_rule, null, 2)}</pre></details></article>)}
      <p>MatchCandidate: {detail.match_candidate_id}</p><p>Алгоритм: {detail.basis.engine_version} · Config: {detail.basis.config_hash}</p><p>Matching profile: {detail.basis.matching_profile_hash}</p><p>Авторитетный источник не задан. Forest Codex не настроен.</p><details><summary>Basis и основания идентичности</summary><pre>{JSON.stringify(detail.basis, null, 2)}</pre></details>
      <section aria-label="Источники нормализации"><h3>Оба запуска нормализации</h3>{detail.normalization_origins.map((origin) => <p key={origin.analysis_id}>Запуск: {origin.analysis_id} · Источник: {origin.source_id} · Профиль: {origin.profile_id} v{origin.profile_version} · SHA-256: {origin.mapping_hash} · Алгоритм: {origin.engine_version}</p>)}</section>
    </section>}
  </main>;
}
