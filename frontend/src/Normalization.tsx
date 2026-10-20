import { useEffect, useState } from 'react';
import { requestJson as api, SessionExpired, type User } from './api';

type Profile = { id: string; code: string; version: string; synthetic: boolean };
type Run = { id: string; status: string; template_id: string; mapping_hash: string; records_processed: number; values_processed: number; quality_counts: Record<string, number>; error_text: string | null; mapping_snapshot: { version: string; engine_version: string; bindings: { fields: { attribute_code: string; path: unknown[] }[] }[] } };
type Value = { rule_definition: { path: unknown[]; [key: string]: unknown }; id: string; attribute_code: string; raw_value: unknown; normalized_value: unknown; unit: string | null; quality_status: string; normalization_rule: { mapping: string; field: string; code: string; presence: string; conversion?: unknown } };
type RecordView = { raw_record_id: string; source_record_key: string | null; source_position: unknown; raw_payload: unknown; source: { name: string; code: string }; import_batch: { id: string; original_filename: string; file_hash: string }; entity: { id: string; domain: string; entity_type: string; display_name: string } | null; values: Value[]; mapping_details: { code: string; unmapped_fields: string[] } };
const statuses: Record<string, string> = { NEW: 'Принят', QUEUED: 'В очереди', PROCESSING: 'Нормализация выполняется', COMPLETED: 'Нормализация завершена', FAILED: 'Нормализация прервана' };

export function Normalization({ batchId, importReady, user, onSessionExpired }: { batchId: string; importReady: boolean; user: User; onSessionExpired: () => void }) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profileId, setProfileId] = useState('');
  const [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState('');
  const [run, setRun] = useState<Run | null>(null);
  const [records, setRecords] = useState<RecordView[]>([]);
  const [offset, setOffset] = useState(0);
  const [listOffset, setListOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    api<Profile[]>('/analysis/profiles', { signal: controller.signal }).then((items) => {
      if (!controller.signal.aborted) {
        setProfiles(items);
        setProfileId(items.find((item) => item.code === 'synthetic-material')?.id ?? items[0]?.id ?? '');
      }
    }).catch((cause) => {
      if (!controller.signal.aborted) {
        if (cause instanceof SessionExpired) onSessionExpired();
        else setError('Не удалось загрузить профили нормализации.');
      }
    });
    return () => controller.abort();
  }, [onSessionExpired]);

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;
    async function load() {
      try {
        const items = await api<Run[]>(`/analysis?import_batch_id=${batchId}&limit=10&offset=${listOffset}`, { signal: controller.signal });
        if (!controller.signal.aborted) { setRuns(items); setRunId((current) => current || items[0]?.id || ''); }
      } catch (cause) {
        if (!controller.signal.aborted) {
          if (cause instanceof SessionExpired) onSessionExpired();
          else setError('Не удалось загрузить историю нормализации.');
        }
      }
      if (!controller.signal.aborted) timer = window.setTimeout(() => { void load(); }, 2000);
    }
    void load();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [batchId, listOffset, refresh, onSessionExpired]);

  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    let timer: number | undefined;
    function failed(cause: unknown) {
      if (!controller.signal.aborted) {
        if (cause instanceof SessionExpired) onSessionExpired();
        else setError('Не удалось обновить результаты нормализации.');
      }
    }
    async function load() {
      await Promise.all([
        api<Run>(`/analysis/${runId}`, { signal: controller.signal }).then((detail) => {
          if (!controller.signal.aborted) setRun(detail);
        }).catch(failed),
        api<RecordView[]>(`/analysis/${runId}/records?limit=50&offset=${offset}`, { signal: controller.signal }).then((items) => {
          if (!controller.signal.aborted) setRecords(items);
        }).catch(failed),
      ]);
      if (!controller.signal.aborted) timer = window.setTimeout(() => { void load(); }, 2000);
    }
    void load();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [runId, offset, refresh, onSessionExpired]);

  function choose(id: string) { setRunId(id); setRun(null); setRecords([]); setOffset(0); }
  async function start() {
    setBusy(true); setError('');
    try {
      const result = await api<Run>('/analysis', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ import_batch_ids: [batchId], template_id: profileId }) });
      choose(result.id); setRun(result); setListOffset(0); setRuns((current) => [result, ...current.filter((item) => item.id !== result.id)]); setRefresh((value) => value + 1);
    } catch (cause) {
      if (cause instanceof SessionExpired) onSessionExpired();
      else setError(cause instanceof TypeError ? 'Не удалось подключиться к серверу.' : cause instanceof Error ? cause.message : 'Не удалось запустить нормализацию.');
    } finally { setBusy(false); }
  }

  return <section className="normalization panel" aria-label="Нормализация">
    <h3>Исходное и нормализованное</h3>
    <p>Нормализация приводит значения к сопоставимому виду. Она не устанавливает истину и не объединяет записи из разных источников.</p>
    {error && <p role="alert" className="warning">{error}</p>}
    <label>Профиль нормализации<select value={profileId} onChange={(event) => setProfileId(event.target.value)}>{profiles.map((item) => <option key={item.id} value={item.id}>{item.code} v{item.version}{item.synthetic ? ' — синтетический тестовый профиль' : ''}</option>)}</select></label>
    {user.permissions.includes('analysis.run') && <button disabled={busy || !profileId || !importReady} onClick={() => void start()}>{busy ? 'Запускаем…' : 'Нормализовать пакет'}</button>}
    {!importReady && <p>Запуск доступен после успешного завершения импорта.</p>}
    <label>Запуск нормализации<select value={runId} onChange={(event) => choose(event.target.value)}><option value="">Выберите запуск</option>{runs.map((item) => <option key={item.id} value={item.id}>{item.id} · {statuses[item.status]}</option>)}</select></label>
    <button disabled={!listOffset} onClick={() => { choose(''); setListOffset(Math.max(0, listOffset - 10)); }}>Предыдущие запуски</button>
    <button disabled={runs.length < 10} onClick={() => { choose(''); setListOffset(listOffset + 10); }}>Следующие запуски</button>
    {run && <>
      <p role="status">{statuses[run.status]} · записей {run.records_processed}, значений {run.values_processed}</p>
      {run.status !== 'COMPLETED' && <p className="warning">Результаты частичные. Запуск ещё не завершён успешно.</p>}
      {run.error_text && <p className="warning">Обработка прервана ({run.error_text}). Можно создать новый запуск; история сохранена.</p>}
      <p>Mapping v{run.mapping_snapshot.version} · правила {run.mapping_snapshot.engine_version}</p>
      <p className="checksum">SHA-256 mapping: {run.mapping_hash}</p>
      {records.map((record) => <details key={record.raw_record_id} className="normalization-record">
        <summary>Запись {record.source_record_key ?? record.raw_record_id} · {record.entity?.display_name ?? 'Объект без mapping'}</summary>
        <p>Источник: {record.source.name} ({record.source.code}) · {record.import_batch.original_filename} · пакет {record.import_batch.id}</p>
        <p className="checksum">SHA-256 оригинала: {record.import_batch.file_hash}</p>
        <pre>Позиция: {JSON.stringify(record.source_position)}</pre>
        {record.entity && <p>Представление одной исходной записи: {record.entity.domain} / {record.entity.entity_type} · {record.entity.id}</p>}
        <div className="table-scroll"><table><thead><tr><th>Канонический атрибут / source field</th><th>Исходное значение</th><th>Нормализованное значение</th><th>Единица</th><th>Качество</th><th>Правило / основание</th></tr></thead><tbody>
          {record.values.map((value) => <tr key={value.id} data-attribute={value.attribute_code}>
            <td>{value.attribute_code}<pre>{JSON.stringify(value.rule_definition.path)}</pre></td>
            <td><pre>{JSON.stringify(value.raw_value)}</pre></td><td><pre>{JSON.stringify(value.normalized_value)}</pre></td><td>{value.unit ?? '—'}</td><td>{value.quality_status}</td>
            <td><pre>{JSON.stringify({ definition: value.rule_definition, evidence: value.normalization_rule }, null, 2)}</pre></td>
          </tr>)}
        </tbody></table></div>
        {!!record.mapping_details.unmapped_fields.length && <p>Поля без mapping (UNKNOWN): {record.mapping_details.unmapped_fields.join(', ')}</p>}
        {record.mapping_details.code !== 'OK' && <p>UNKNOWN: {record.mapping_details.code}</p>}
        <details><summary>Исходная запись целиком</summary><pre>{JSON.stringify(record.raw_payload, null, 2)}</pre></details>
      </details>)}
      <button disabled={!offset} onClick={() => { setRecords([]); setOffset(Math.max(0, offset - 50)); }}>Предыдущие нормализованные записи</button>
      <button disabled={records.length < 50} onClick={() => { setRecords([]); setOffset(offset + 50); }}>Следующие нормализованные записи</button>
    </>}
  </section>;
}
