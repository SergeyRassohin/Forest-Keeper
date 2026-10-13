export interface Health {
  status: 'ok' | 'degraded';
  components: Record<'api' | 'database' | 'redis', 'ok' | 'unavailable'>;
}

export async function readHealth(signal: AbortSignal): Promise<Health> {
  const response = await fetch('/api/v1/health', { signal, cache: 'no-store' });
  if (!response.ok && response.status !== 503) throw new Error('Сервер недоступен');
  const body: unknown = await response.json();
  if (!body || typeof body !== 'object') throw new Error('Некорректный ответ сервера');
  const health = body as Partial<Health>;
  if (
    !['ok', 'degraded'].includes(health.status ?? '') ||
    !health.components ||
    !['api', 'database', 'redis'].every((key) =>
      ['ok', 'unavailable'].includes(health.components![key as keyof Health['components']]),
    )
  ) throw new Error('Некорректный ответ сервера');
  return health as Health;
}
