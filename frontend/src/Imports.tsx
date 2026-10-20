import { useEffect, useState, type FormEvent } from 'react';
import { requestJson as api, SessionExpired, type User } from './api';
import { Normalization } from './Normalization';

interface Source {
  id: string; name: string; code: string; source_type: string; status: string;
}
interface Batch {
  id: string; source_system_id: string; source_name: string; original_filename: string;
  format: string; status: string; file_hash: string; uploaded_at: string; uploaded_by: string;
  records_loaded: number; records_failed: number; error_text: string | null;
  duplicate: boolean;
}
interface Raw {
  id: string; source_record_key: string | null; source_object_type: string;
  raw_payload: Record<string, unknown>; source_position: Record<string, unknown>;
}
interface ParseError {
  id: string; code: string; message: string; source_position: Record<string, unknown>;
}
const labels = new Map(Object.entries({
  NEW: 'Принят', QUEUED: 'В очереди', PROCESSING: 'Обрабатывается',
  COMPLETED: 'Завершён', COMPLETED_WITH_ERRORS: 'Завершён с ошибками', FAILED: 'Ошибка импорта',
}));


export function Imports({ user, onSessionExpired }: { user: User; onSessionExpired: () => void }) {
  const [sources, setSources] = useState<Source[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [selected, setSelected] = useState('');
  const [batch, setBatch] = useState<Batch | null>(null);
  const [records, setRecords] = useState<Raw[]>([]);
  const [errors, setErrors] = useState<ParseError[]>([]);
  const [refresh, setRefresh] = useState(0);
  const [listOffset, setListOffset] = useState(0);
  const [rawOffset, setRawOffset] = useState(0);
  const [errorOffset, setErrorOffset] = useState(0);
  const [sourceId, setSourceId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [sourceName, setSourceName] = useState('');
  const [sourceCode, setSourceCode] = useState('');
  const [sourceType, setSourceType] = useState('FILE');

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;
    async function load() {
      try {
        const [sourceRows, importRows] = await Promise.all([
          api<Source[]>('/sources?limit=100', { signal: controller.signal }),
          api<Batch[]>(`/imports?limit=50&offset=${listOffset}`, { signal: controller.signal }),
        ]);
        if (!controller.signal.aborted) { setSources(sourceRows); setBatches(importRows); }
      } catch (cause) {
        if (!controller.signal.aborted) {
          if (cause instanceof SessionExpired) onSessionExpired();
          else setError('Не удалось обновить список импортов. Проверьте подключение.');
        }
      }
      if (!controller.signal.aborted) timer = window.setTimeout(() => { void load(); }, 2000);
    }
    void load();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [listOffset, refresh, onSessionExpired]);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    let timer: number | undefined;
    function failed(cause: unknown) {
      if (!controller.signal.aborted) {
        if (cause instanceof SessionExpired) onSessionExpired();
        else setError('Не удалось загрузить пакет импорта. Повторите попытку.');
      }
    }
    async function load() {
      // Metadata can appear while raw data is still loading. Wait for each
      // request to finish before polling again; only navigation cancels it.
      await Promise.all([
        api<Batch>(`/imports/${selected}`, { signal: controller.signal }).then((detail) => {
          if (!controller.signal.aborted) setBatch(detail);
        }).catch(failed),
        api<Raw[]>(`/imports/${selected}/records?limit=50&offset=${rawOffset}`, { signal: controller.signal }).then((raw) => {
          if (!controller.signal.aborted) setRecords(raw);
        }).catch(failed),
        api<ParseError[]>(`/imports/${selected}/errors?limit=50&offset=${errorOffset}`, { signal: controller.signal }).then((problems) => {
          if (!controller.signal.aborted) setErrors(problems);
        }).catch(failed),
      ]);
      if (!controller.signal.aborted) timer = window.setTimeout(() => { void load(); }, 2000);
    }
    void load();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [selected, refresh, rawOffset, errorOffset, onSessionExpired]);

  function choose(id: string) {
    setSelected(id); setRawOffset(0); setErrorOffset(0); setBatch(null);
    setRecords([]); setErrors([]); setRefresh((value) => value + 1);
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file || !sourceId) return;
    setBusy(true); setError(''); setNotice('');
    const body = new FormData(); body.set('source_id', sourceId); body.set('file', file);
    try {
      const result = await api<Batch>('/imports', { method: 'POST', body });
      setNotice(result.duplicate
        ? `Этот файл уже загружен: ${result.original_filename}. Открыт существующий пакет.`
        : 'Файл сохранён. Статус фоновой обработки показан ниже.');
      choose(result.id);
    } catch (cause) {
      if (cause instanceof SessionExpired) onSessionExpired();
      else setError(cause instanceof TypeError ? 'Не удалось подключиться к серверу.' :
        cause instanceof Error ? cause.message : 'Не удалось загрузить файл.');
    } finally { setBusy(false); }
  }

  async function createSource(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const created = await api<Source>('/sources', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: sourceName, code: sourceCode, source_type: sourceType }),
      });
      setSources((current) => [...current, created]); setSourceId(created.id);
      setSourceName(''); setSourceCode(''); setNotice('Источник создан.');
    } catch (cause) {
      if (cause instanceof SessionExpired) onSessionExpired();
      else setError(cause instanceof TypeError ? 'Не удалось подключиться к серверу.' :
        cause instanceof Error ? cause.message : 'Не удалось создать источник.');
    } finally { setBusy(false); }
  }

  async function retry() {
    if (!batch) return;
    setBusy(true); setError('');
    try {
      const result = await api<Batch>(`/imports/${batch.id}/retry`, { method: 'POST' });
      choose(result.id); setNotice('Создан новый пакет повторного импорта.');
    } catch (cause) {
      if (cause instanceof SessionExpired) onSessionExpired();
      else setError(cause instanceof TypeError ? 'Не удалось подключиться к серверу.' :
        cause instanceof Error ? cause.message : 'Не удалось повторить импорт.');
    } finally { setBusy(false); }
  }

  return <main className="shell imports">
    <h1>Импорт данных</h1>
    <p>Загрузите исходные файлы. Forest Keeper сохранит оригинал и покажет записи с их происхождением.</p>
    {error && <p role="alert" className="warning">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {user.permissions.includes('source.manage') && <details className="panel">
      <summary>Добавить источник</summary>
      <form onSubmit={createSource}>
        <label>Название источника<input required maxLength={200} value={sourceName} onChange={(event) => setSourceName(event.target.value)} /></label>
        <label>Код источника<input required maxLength={64} pattern="[A-Za-z0-9_-]+" value={sourceCode} onChange={(event) => setSourceCode(event.target.value)} /></label>
        <label>Тип источника<select value={sourceType} onChange={(event) => setSourceType(event.target.value)}><option value="FILE">Файловая выгрузка</option><option value="ONE_C">Выгрузка 1С</option></select></label>
        <button disabled={busy}>Создать источник</button>
      </form>
    </details>}
    {user.permissions.includes('import.create') && <section className="panel">
      <h2>Загрузить файл</h2>
      <form onSubmit={upload}>
        <label>Источник<select required value={sourceId} onChange={(event) => setSourceId(event.target.value)}>
          <option value="">Выберите источник</option>
          {sources.filter((source) => source.status === 'ACTIVE').map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}
        </select></label>
        <label>Исходный файл<input type="file" required accept=".csv,.xlsx,.xml" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
        <button disabled={busy}>{busy ? 'Загружаем…' : 'Загрузить'}</button>
      </form>
    </section>}
    <section className="panel">
      <h2>Пакеты импорта</h2>
      {batches.length === 0 && <p>На этой странице пока нет импортов.</p>}
      <div className="table-scroll"><table><thead><tr><th>Файл</th><th>Источник</th><th>Формат</th><th>Статус</th><th>Загружен</th><th>Записей</th><th>Ошибок</th></tr></thead>
        <tbody>{batches.map((item) => <tr key={item.id}>
          <td><button onClick={() => choose(item.id)}>{item.original_filename}</button></td>
          <td>{item.source_name}</td><td>{item.format}</td><td>{labels.get(item.status)}</td>
          <td>{new Date(item.uploaded_at).toLocaleString()}</td><td>{item.records_loaded}</td><td>{item.records_failed}</td>
        </tr>)}</tbody></table></div>
      <button disabled={listOffset === 0} onClick={() => setListOffset(Math.max(0, listOffset - 50))}>Предыдущие пакеты</button>
      <button disabled={batches.length < 50} onClick={() => setListOffset(listOffset + 50)}>Следующие пакеты</button>
    </section>
    {batch && <section className="panel" aria-label="Карточка импорта">
      <h2>{batch.original_filename}</h2>
      <dl><dt>Статус</dt><dd>{labels.get(batch.status)}</dd><dt>Источник</dt><dd>{batch.source_name}</dd>
        <dt>Идентификатор пакета</dt><dd>{batch.id}</dd><dt>Формат</dt><dd>{batch.format}</dd>
        <dt>Контрольная сумма SHA-256</dt><dd className="checksum">{batch.file_hash}</dd>
        <dt>Загрузил</dt><dd>{batch.uploaded_by}</dd><dt>Загружен</dt><dd>{new Date(batch.uploaded_at).toLocaleString()}</dd>
        <dt>Исходных записей</dt><dd>{batch.records_loaded}</dd><dt>Ошибок</dt><dd>{batch.records_failed}</dd>
      </dl>
      {batch.error_text && <p className="warning">{batch.error_text}</p>}
      {user.permissions.includes('import.retry') && ['FAILED', 'COMPLETED_WITH_ERRORS'].includes(batch.status) &&
        <button disabled={busy} onClick={() => void retry()}>Повторить импорт новым пакетом</button>}
      <h3>Ошибки разбора</h3>
      {errors.length === 0 ? <p>Ошибок на этой странице нет.</p> : <ul>{errors.map((item) => <li key={item.id}>{item.message} · {JSON.stringify(item.source_position)}</li>)}</ul>}
      <button disabled={errorOffset === 0} onClick={() => setErrorOffset(Math.max(0, errorOffset - 50))}>Предыдущие ошибки</button>
      <button disabled={errors.length < 50} onClick={() => setErrorOffset(errorOffset + 50)}>Следующие ошибки</button>
      {user.permissions.includes('analysis.view') && <Normalization key={batch.id} batchId={batch.id} importReady={['COMPLETED', 'COMPLETED_WITH_ERRORS'].includes(batch.status)} user={user} onSessionExpired={onSessionExpired} />}
      <h3>Исходные записи</h3>
      <div className="table-scroll"><table><thead><tr><th>Ключ / тип</th><th>Позиция в источнике</th><th>Исходные значения</th></tr></thead>
        <tbody>{records.map((record) => <tr key={record.id}><td>{record.source_record_key ?? '—'} / {record.source_object_type}</td><td><pre>{JSON.stringify(record.source_position, null, 2)}</pre></td><td><pre>{JSON.stringify(record.raw_payload, null, 2)}</pre></td></tr>)}</tbody></table></div>
      <button disabled={rawOffset === 0} onClick={() => setRawOffset(Math.max(0, rawOffset - 50))}>Предыдущие записи</button>
      <button disabled={records.length < 50} onClick={() => setRawOffset(rawOffset + 50)}>Следующие записи</button>
    </section>}
  </main>;
}
