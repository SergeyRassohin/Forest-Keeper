import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const accounts = JSON.parse(readFileSync(resolve(process.cwd(), '../deploy/local/e2e.json'), 'utf8'));

async function signIn(page: Page, role: 'ADMIN' | 'VIEWER') {
  await page.goto('/');
  await page.getByLabel('Логин', { exact: true }).fill(accounts[role].login);
  await page.getByLabel('Пароль', { exact: true }).fill(accounts[role].password);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await page.getByRole('button', { name: 'Импорт данных', exact: true }).click();
}

async function prepare(page: Page, kind: 'csv' | 'onec' | 'public-csv' | 'public-xml') {
  const source = page.locator('details').filter({ hasText: 'Добавить источник' });
  if (!(await source.evaluate((element) => (element as HTMLDetailsElement).open))) await source.locator('summary').click();
  await page.getByLabel('Название источника', { exact: true }).fill('Нормализация ' + kind + ' ' + accounts.prefix);
  await page.getByLabel('Код источника', { exact: true }).fill(accounts.prefix + '_norm_' + kind);
  await page.getByRole('combobox', { name: 'Тип источника', exact: true }).selectOption(kind === 'onec' ? 'ONE_C' : 'FILE');
  await page.getByRole('button', { name: 'Создать источник', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Источник создан' })).toBeVisible();
  const file = kind === 'public-csv' ? 'source-a.csv' : kind === 'public-xml' ? 'source-b.xml' : kind === 'csv' ? 'material.csv' : 'onec.xml';
  const directory = kind.startsWith('public-') ? 'external-review' : 'normalization';
  await page.getByLabel('Исходный файл', { exact: true }).setInputFiles(resolve(process.cwd(), '../tests/data', directory, file));
  const upload = page.waitForResponse((response) => response.url().endsWith('/api/v1/imports') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Загрузить', exact: true }).click();
  const batch = await (await upload).json();
  const card = page.getByRole('region', { name: 'Карточка импорта', exact: true });
  await expect(card).toContainText(batch.id);
  await expect(card).toContainText('Завершён', { timeout: 30000 });
  return batch.id as string;
}

test('normalizes two sources without matching and preserves original mass, quality, rule and provenance', async ({ page }) => {
  test.setTimeout(120000);
  await signIn(page, 'ADMIN');
  const entityIds: string[][] = [];
  for (const kind of ['csv', 'onec'] as const) {
    const batch = await prepare(page, kind);
    const before = await (await page.request.get(`/api/v1/imports/${batch}/records`)).json();
    const section = page.getByRole('region', { name: 'Нормализация', exact: true });
    await expect(section.getByLabel('Профиль нормализации')).toContainText('синтетический тестовый профиль');
    const pending = page.waitForResponse((response) => response.url().endsWith('/api/v1/analysis') && response.request().method() === 'POST');
    await section.getByRole('button', { name: 'Нормализовать пакет', exact: true }).click();
    const run = await (await pending).json();
    await expect(section.getByRole('status')).toContainText('Нормализация завершена', { timeout: 30000 });
    for (const [index, raw] of ['12,5 кг', '12500 г', '12.500 KG'].entries()) {
      await section.getByText(new RegExp(`^Запись 00${index + 1} ·`)).click();
      const record = section.locator('.normalization-record').filter({ has: page.getByText(new RegExp(`^Запись 00${index + 1} ·`)) });
      const mass = record.locator('tr[data-attribute="mass"]');
      await expect(mass.getByRole('cell').nth(1)).toHaveText(String(raw));
      await expect(mass.getByRole('cell').nth(2)).toHaveText('12.5');
      await expect(mass.getByRole('cell').nth(3)).toHaveText('kg');
      await expect(mass.getByRole('cell').nth(4)).toContainText('VALID');
      await expect(mass.getByRole('cell').nth(5)).toContainText('quantity');
      await expect(mass.getByRole('cell').nth(5)).toContainText('factor');
      await expect(record).toContainText('Нормализация ' + kind + ' ' + accounts.prefix);
      await expect(record).toContainText('SHA-256 оригинала');
      await expect(record).toContainText('Позиция');
    }
    await section.getByText(/^Запись 004 ·/).click();
    const invalid = section.locator('.normalization-record').filter({ has: page.getByText(/^Запись 004 ·/) });
    await expect(invalid.locator('tr[data-attribute="mass"]')).toContainText('UNKNOWN');
    await expect(invalid.locator('tr[data-attribute="manufactured_on"]')).toContainText('INVALID');
    await expect(invalid).toContainText('UNKNOWN_UNIT');
    await expect(section).toContainText('не устанавливает истину');
    expect(await (await page.request.get(`/api/v1/imports/${batch}/records`)).json()).toEqual(before);
    const results = await (await page.request.get(`/api/v1/analysis/${run.id}/records`)).json();
    entityIds.push(results.map((record: { entity: { id: string } }) => record.entity.id));
  }
  expect(entityIds[0].some((id) => entityIds[1].includes(id))).toBe(false);
  await page.getByRole('button', { name: 'Выйти', exact: true }).click();
  await signIn(page, 'VIEWER');
  await page.getByRole('row').filter({ hasText: 'Нормализация csv ' + accounts.prefix }).getByRole('button', { name: 'material.csv', exact: true }).click();
  const section = page.getByRole('region', { name: 'Нормализация', exact: true });
  await expect(section.getByRole('status')).toContainText('Нормализация завершена');
  await expect(section.getByRole('button', { name: 'Нормализовать пакет' })).toHaveCount(0);
});


test('external reviewer imports public USGS CSV/XML and sees documented normalization and unchanged raw', async ({ page }) => {
  test.setTimeout(120000);
  await signIn(page, 'ADMIN');
  const normalized: unknown[] = [];
  for (const kind of ['public-csv', 'public-xml'] as const) {
    const batch = await prepare(page, kind);
    const rawUrl = `/api/v1/imports/${batch}/records?limit=100`;
    const before = await (await page.request.get(rawUrl)).json();
    expect(before).toHaveLength(60);
    const section = page.getByRole('region', { name: 'Нормализация', exact: true });
    await section.getByLabel('Профиль нормализации').selectOption({ label: 'public-earthquake v1' });
    const pending = page.waitForResponse((response) => response.url().endsWith('/api/v1/analysis') && response.request().method() === 'POST');
    await section.getByRole('button', { name: 'Нормализовать пакет', exact: true }).click();
    const run = await (await pending).json();
    await expect(section.getByRole('status')).toContainText('Нормализация завершена', { timeout: 30000 });
    await expect(section.getByRole('status')).toContainText('записей 60, значений 240');
    const detail = await (await page.request.get(`/api/v1/analysis/${run.id}`)).json();
    expect(detail.quality_counts.VALID).toBe(240);
    const records = await (await page.request.get(`/api/v1/analysis/${run.id}/records?limit=100`)).json();
    expect(records).toHaveLength(60);
    const event = records.find((record: { values: { attribute_code: string; normalized_value: unknown }[] }) => record.values.some((value) => value.attribute_code === 'code' && value.normalized_value === 'us6000pjr6'));
    expect(event).toBeTruthy();
    const values = Object.fromEntries(event.values.map((value: { attribute_code: string; normalized_value: unknown }) => [value.attribute_code, value.normalized_value]));
    expect(values.code).toBe('us6000pjr6');
    expect(values.magnitude).toBe('4.2');
    expect(values.occurred_at).toBe('2025-01-01T00:13:22.650Z');
    normalized.push(values);
    const card = section.locator('.normalization-record').first();
    await card.locator('summary').first().click();
    await expect(card).toContainText('demo-earthquake / EarthquakeEvent');
    await expect(card).toContainText('SHA-256 оригинала');
    expect(await (await page.request.get(rawUrl)).json()).toEqual(before);
  }
  expect(normalized[0]).toEqual(normalized[1]);
});
