import type { ReactNode } from 'react';

const labels = new Map(Object.entries({
  NEW: 'Принят', QUEUED: 'В очереди', PROCESSING: 'Обрабатывается',
  COMPLETED: 'Завершено', COMPLETED_WITH_ERRORS: 'Завершено с ошибками', FAILED: 'Ошибка',
  MATCHED: 'Сопоставлено', POSSIBLE_MATCH: 'Требует проверки', NOT_MATCHED: 'Не сопоставлено',
  OPEN: 'Открыт', IN_REVIEW: 'На рассмотрении', RESOLVED: 'Решён', INSUFFICIENT_DATA: 'Недостаточно данных',
  VALID: 'Корректно', INVALID: 'Некорректно', UNKNOWN: 'Не определено', WARNING: 'Требует внимания',
  LOW: 'Низкая', ACTIVE: 'Активен',
}));
const success = new Set(['COMPLETED', 'MATCHED', 'VALID', 'ACTIVE']);
const danger = new Set(['FAILED', 'INVALID']);
const warning = new Set(['POSSIBLE_MATCH', 'COMPLETED_WITH_ERRORS', 'WARNING']);
export function StatusBadge({ value, label, code = true }: { value: string; label?: string; code?: boolean }) {
  const tone = success.has(value) ? 'success' : danger.has(value) ? 'danger' : warning.has(value) ? 'warning' : 'neutral';
  return <span className={'badge badge-' + tone}><span>{label ?? labels.get(value) ?? value}</span>{code && <small className="badge-code">{value}</small>}</span>;
}
export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty-state"><span className="empty-symbol" aria-hidden="true">↳</span><h3>{title}</h3>{children && <p>{children}</p>}</div>;
}
export function DataValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="muted">Не задано</span>;
  if (typeof value === 'object') return <dl className="data-fields">{Object.entries(value).map(([key, field]) => <div key={key}><dt>{key}</dt><dd>{typeof field === 'object' ? JSON.stringify(field) : String(field)}</dd></div>)}</dl>;
  return <span className="data-value">{String(value)}</span>;
}
export function Identifier({ children }: { children: ReactNode }) {
  return <code className="identifier">{children}</code>;
}
