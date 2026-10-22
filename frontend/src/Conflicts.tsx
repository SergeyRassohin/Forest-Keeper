import { useEffect, useState } from 'react';
import { StatusBadge, EmptyState, DataValue, Identifier } from './ui';
import { requestJson as api, SessionExpired, type User } from './api';

type Run = { id: string; status: string; matching_run_id: string; records_processed: number; conflicts_generated: number; error_text: string | null };
type Row = { id: string; entity_id: string; matching_run_id: string; attribute_code: string; conflict_type: string; severity: string; status: string; detected_at: string; sources?: { source_name: string; source_record_key: string }[] };
type Value = { source_name: string; source_id: string; source_record_key: string; raw_record_id: string; entity_id: string; filename: string; file_hash: string; source_position: unknown; presence: string; value: { raw_value: unknown; raw_value_omitted: boolean; normalized_value: unknown; unit: string | null; quality_status: string; normalization_rule: unknown } | null };
type Detail = Row & { match_candidate_id: string; values_snapshot: Value[]; normalization_origins: { analysis_id: string; source_id: string; profile_id: string; profile_version: string; mapping_hash: string; engine_version: string }[]; basis: { reason_code: string; engine_version: string; config_hash: string; matching_profile_hash: string; matching_evidence: unknown; normalization_context: unknown }; based_on_previous_profile: boolean };

export function Conflicts({ user, onSessionExpired, initialRunId = '' }: { user: User; onSessionExpired: () => void; initialRunId?: string }) {
  const [loaded, setLoaded] = useState(false);
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
        if (!controller.signal.aborted) { setRows(items); setRuns(history); setMatchingRuns(inputs); setDetail(card); setError(''); setLoaded(true); }
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
  const types = new Map(Object.entries({ VALUE_MISMATCH: 'Разные значения', MISSING: 'Отсутствует значение', DUPLICATE: 'Повторяющаяся запись', RULE_VIOLATION: 'Нарушение правила', ANOMALY: 'Аномалия' }));
  const attributes = new Map(Object.entries({ mass: 'Масса', name: 'Наименование', code: 'Код', price: 'Цена', date: 'Дата' }));
  return <main className="shell" aria-label="Конфликты">
    <div className="page-heading"><p className="eyebrow">Проверка согласованности</p><h1>Конфликты</h1><p>Расхождения в подтверждённых парах. Сравните значения и посмотрите, откуда они поступили.</p></div>
    {error && <p role="alert">{error}</p>}
    <section className="panel" aria-label="Проверка конфликтов"><div className="panel-heading"><h2>Проверить сопоставленные записи</h2><span className="badge">Этап 5 · обнаружение расхождений</span></div>
      <label>Сопоставление для конфликтов<select value={matching} onChange={(event) => { setMatching(event.target.value); setOffset(0); setDetailId(''); setDetail(null); }}><option value="">Все сопоставления</option>{matching && !matchingRuns.some((item) => item.id === matching) && <option value={matching}>{matching}</option>}{matchingRuns.filter((item) => item.status === 'COMPLETED').map((item) => <option key={item.id}>{item.id}</option>)}</select></label>
      {user.permissions.includes('analysis.run') && <button className="primary" disabled={!matching || busy} onClick={() => void start()}>Проверить конфликты</button>}
      {runs.filter((item) => !matching || item.matching_run_id === matching).map((item) => <div className="execution-summary" role="status" key={item.id}><StatusBadge value={item.status} /><p>Проверено пар: <strong>{item.records_processed}</strong> · Конфликтов в запуске: <strong>{item.conflicts_generated}</strong> (включая ранее сохранённые)</p><Identifier>{item.id}</Identifier>{item.error_text && <p className="warning">{item.error_text}</p>}</div>)}
    </section>
    <section className="panel" aria-label="Список конфликтов"><div className="panel-heading"><h2>Найденные расхождения</h2><span className="muted">Окончательное решение остаётся за человеком</span></div>
      <label>Тип конфликта<select value={filter} onChange={(event) => { setFilter(event.target.value); setOffset(0); setDetailId(''); setDetail(null); }}><option value="">Все типы</option>{['VALUE_MISMATCH','MISSING','DUPLICATE','RULE_VIOLATION','ANOMALY'].map((kind) => <option key={kind} value={kind}>{types.get(kind)}</option>)}</select></label>
      <p className="muted">LOW — нейтральная техническая оценка; бизнес-политика важности пока не настроена.</p>
      {!loaded && !error && <p role="status">Загружаем конфликты…</p>}
      {!!rows.length && <div className="table-scroll" tabIndex={0} role="region" aria-label="Таблица конфликтов"><table><thead><tr>{['Расхождение','Источники','Тип','Важность','Статус','Обнаружен'].map((label) => <th key={label}>{label}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td><button aria-label={'Открыть конфликт ' + row.id} onClick={() => { setDetail(null); setDetailId(row.id); }}><strong>{attributes.get(row.attribute_code) ?? row.attribute_code}</strong><br /><Identifier>#{row.id.slice(0, 8)}</Identifier></button></td><td>{row.sources?.map((item) => <div key={item.source_name + item.source_record_key}>{item.source_name}<small className="record-key">{item.source_record_key}</small></div>)}</td><td><StatusBadge value={row.conflict_type} label={types.get(row.conflict_type)} /></td><td><StatusBadge value={row.severity} /></td><td><StatusBadge value={row.status} /></td><td>{new Date(row.detected_at).toLocaleString()}</td></tr>)}</tbody></table></div>}
      {loaded && !rows.length && <EmptyState title="Конфликты не найдены">Выберите завершённое сопоставление и проверьте его. Отсутствие результатов до завершения анализа не означает, что расхождений нет.</EmptyState>}
      <div className="pagination"><button disabled={!offset} onClick={() => { setOffset(Math.max(0, offset - 50)); setDetailId(''); setDetail(null); }}>Предыдущие конфликты</button><button disabled={rows.length < 50} onClick={() => { setOffset(offset + 50); setDetailId(''); setDetail(null); }}>Следующие конфликты</button></div>
    </section>
    {detail && <section className="panel" aria-label="Карточка конфликта">
      <div className="panel-heading"><div><p className="eyebrow">Разбор расхождения</p><h2>{attributes.get(detail.attribute_code) ?? detail.attribute_code} · {types.get(detail.conflict_type) ?? detail.conflict_type}</h2></div><StatusBadge value={detail.status} /></div>
      <p className="human-boundary">Решение человека ещё не принято. Human Review будет доступен на следующем этапе.</p>
      {detail.based_on_previous_profile && <p className="warning">Результат по предыдущей версии профиля. Для новой оценки запустите анализ заново.</p>}
      <p>{detail.basis.reason_code === 'NORMALIZED_VALUES_DIFFER' ? 'Нормализованные значения одного атрибута различаются.' : detail.basis.reason_code === 'SOURCE_VALUE_ABSENT' ? 'Значение отсутствует в одном источнике; причина указана для каждой стороны.' : 'Несколько записей одного источника подтверждены как одна сущность.'}</p>
      <div className="comparison-grid">{detail.values_snapshot.map((item, index) => <article className="source-card" key={item.raw_record_id}><p className="eyebrow">Источник {index === 0 ? 'A' : 'B'}</p><h3>{item.source_name} · {item.source_record_key}</h3>
        <p className="value-label">Исходное значение</p><div className="compared-value">{item.value?.raw_value_omitted ? <span>Сохранено в оригинале</span> : <DataValue value={item.value?.raw_value} />}</div>{item.value?.raw_value_omitted && <p className="muted">Полное длинное значение сохранено в исходной записи.</p>}
        <p className="value-label">После нормализации</p><div className="compared-value normalized-value"><DataValue value={item.value?.normalized_value} /> {item.value?.unit}</div>
        <p><StatusBadge value={item.value?.quality_status ?? 'UNKNOWN'} /> <span className="muted">Наличие: {item.presence}</span></p>
        <p>Файл: {item.filename}</p><details><summary>Происхождение и правило нормализации</summary><dl><dt>Источник / запись</dt><dd><Identifier>{item.source_id} · {item.raw_record_id}</Identifier></dd><dt>SHA-256 оригинала</dt><dd><Identifier>{item.file_hash}</Identifier></dd><dt>Позиция</dt><dd><DataValue value={item.source_position} /></dd></dl><pre>{JSON.stringify(item.value?.normalization_rule, null, 2)}</pre></details>
      </article>)}</div>
      <p className="muted">Авторитетный источник не задан. Нормализованное значение не является истиной. Forest Codex не настроен.</p>
      <section aria-label="Источники нормализации"><h3>Оба запуска нормализации</h3><div className="comparison-grid">{detail.normalization_origins.map((origin) => <div key={origin.analysis_id}><p>Профиль v{origin.profile_version} · {origin.engine_version}</p><Identifier>Запуск: {origin.analysis_id} · Источник: {origin.source_id}</Identifier><details><summary>Версия и контрольная сумма профиля</summary><Identifier>Профиль: {origin.profile_id} v{origin.profile_version} · SHA-256: {origin.mapping_hash}</Identifier></details></div>)}</div></section>
      <details><summary>Технические идентификаторы, Basis и основания идентичности</summary><p>Conflict ID: <Identifier>{detail.id}</Identifier></p><p>MatchCandidate: <Identifier>{detail.match_candidate_id}</Identifier></p><p>Алгоритм: {detail.basis.engine_version} · Config: <Identifier>{detail.basis.config_hash}</Identifier></p><p>Matching profile: <Identifier>{detail.basis.matching_profile_hash}</Identifier></p><pre>{JSON.stringify(detail.basis, null, 2)}</pre></details>
    </section>}
  </main>;
}
