import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
const accounts = JSON.parse(readFileSync(resolve(process.cwd(), '../deploy/local/e2e.json'), 'utf8'));
async function signIn(page: Page, role: 'ADMIN' | 'REVIEWER' | 'VIEWER') {
  await page.goto('/'); await page.getByLabel('Логин', { exact: true }).fill(accounts[role].login); await page.getByLabel('Пароль', { exact: true }).fill(accounts[role].password); await page.getByRole('button', { name: 'Войти', exact: true }).click();
}
async function input(page: Page, side: 'a' | 'b') {
  await page.getByRole('button', { name: 'Импорт данных', exact: true }).click();
  const source = page.locator('details').filter({ hasText: 'Добавить источник' });
  if (!(await source.evaluate((element) => (element as HTMLDetailsElement).open))) await source.locator('summary').click();
  await page.getByLabel('Название источника', { exact: true }).fill('Matching ' + side + ' ' + accounts.prefix);
  await page.getByLabel('Код источника', { exact: true }).fill(accounts.prefix + '_match_' + side);
  await page.getByRole('combobox', { name: 'Тип источника', exact: true }).selectOption(side === 'a' ? 'FILE' : 'ONE_C');
  await page.getByRole('button', { name: 'Создать источник', exact: true }).click(); await expect(page.getByRole('status').filter({ hasText: 'Источник создан' })).toBeVisible();
  await page.getByLabel('Исходный файл', { exact: true }).setInputFiles(resolve(process.cwd(), '../tests/data/matching/source-' + side + (side === 'a' ? '.csv' : '.xml')));
  const upload = page.waitForResponse((response) => response.url().endsWith('/api/v1/imports') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Загрузить', exact: true }).click(); const batch = await (await upload).json();
  const card = page.getByRole('region', { name: 'Карточка импорта', exact: true }); await expect(card).toContainText(batch.id); await expect(card).toContainText('Завершён', { timeout: 30000 });
  const normalization = page.getByRole('region', { name: 'Нормализация', exact: true });
  const started = page.waitForResponse((response) => response.url().endsWith('/api/v1/analysis') && response.request().method() === 'POST');
  await normalization.getByRole('button', { name: 'Нормализовать пакет', exact: true }).click(); const run = await (await started).json();
  await expect(normalization.getByRole('status')).toContainText('Нормализация завершена', { timeout: 30000 });
  return run.id as string;
}
async function chooseRun(page: Page, id: string) {
  await page.getByRole('button', { name: 'Сопоставление', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Запуск сопоставления', exact: true })).toContainText(id);
  await page.getByRole('combobox', { name: 'Запуск сопоставления', exact: true }).selectOption(id);
}
test('matches two normalized browser imports with evidence and authorized review, preserving raw history', async ({ page }) => {
  test.setTimeout(180000); await signIn(page, 'ADMIN');
  const ids = [await input(page, 'a'), await input(page, 'b')];
  const before = await Promise.all(ids.map(async (id) => (await page.request.get('/api/v1/analysis/' + id + '/records')).json()));
  await page.getByRole('button', { name: 'Сопоставление', exact: true }).click();
  await page.getByRole('combobox', { name: 'Нормализация источника A', exact: true }).selectOption(ids[0]);
  await page.getByRole('combobox', { name: 'Нормализация источника B', exact: true }).selectOption(ids[1]);
  const started = page.waitForResponse((response) => response.url().endsWith('/api/v1/matching-runs') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Запустить сопоставление', exact: true }).click(); const run = await (await started).json();
  const result = page.getByRole('region', { name: 'Результат сопоставления', exact: true }); await expect(result.getByRole('status')).toContainText('Сопоставление завершено', { timeout: 30000 });
  const filter = page.getByRole('combobox', { name: 'Статус кандидата', exact: true });
  for (const [status,label] of [['MATCHED','Совпадение'],['POSSIBLE_MATCH','Требует проверки'],['NOT_MATCHED','Разные сущности']]) {
    await filter.selectOption(status); await expect(result.getByRole('cell', { name: label, exact: true }).first()).toBeVisible();
  }
  await filter.selectOption('MATCHED');
  const matches = await (await page.request.get('/api/v1/matching-runs/' + run.id + '/candidates?status=MATCHED')).json();
  let selected = matches[0];
  for (const candidate of matches) {
    const detail = await (await page.request.get('/api/v1/match-candidates/' + candidate.id)).json();
    if (detail.records.every((record: { source_record_key: string }) => record.source_record_key === 'MAT001')) selected = candidate;
  }
  await result.getByRole('button', { name: selected.raw_record_a_id + ' ↔ ' + selected.raw_record_b_id, exact: true }).click();
  const detail = page.getByRole('region', { name: 'Основание сопоставления', exact: true });
  await expect(detail).toContainText('12500 г'); await expect(detail).toContainText('12.500 KG'); await expect(detail).toContainText('12.5');
  await expect(detail).toContainText('Matching a ' + accounts.prefix); await expect(detail).toContainText('Matching b ' + accounts.prefix);
  await expect(detail).toContainText('SHA-256 оригинала'); await expect(detail).toContainText('token_sort_ratio'); await expect(detail).toContainText('EXACT_RULES_ONLY_NO_FUZZY_AUTO');
  await expect(detail.getByRole('button', { name: 'Подтвердить совпадение' })).toHaveCount(0);
  const possible = await (await page.request.get('/api/v1/matching-runs/' + run.id + '/candidates?status=POSSIBLE_MATCH')).json();
  let fuzzyCandidate = possible[0];
  for (const candidate of possible) {
    const snapshot = await (await page.request.get('/api/v1/match-candidates/' + candidate.id)).json();
    if (snapshot.records.every((record: { source_record_key: string }) => record.source_record_key === 'MAT003')) fuzzyCandidate = candidate;
  }
  await filter.selectOption('POSSIBLE_MATCH');
  await result.getByRole('button', { name: fuzzyCandidate.raw_record_a_id + ' ↔ ' + fuzzyCandidate.raw_record_b_id, exact: true }).click();
  await expect(detail.getByRole('button', { name: 'Подтвердить совпадение' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Выйти', exact: true }).click(); await signIn(page, 'REVIEWER'); await chooseRun(page, run.id);
  await filter.selectOption('POSSIBLE_MATCH'); await expect(result.getByRole('row').nth(1)).toContainText('Требует проверки');
  await result.getByRole('button', { name: fuzzyCandidate.raw_record_a_id + ' ↔ ' + fuzzyCandidate.raw_record_b_id, exact: true }).click();
  await detail.getByLabel('Причина подтверждения или отклонения').fill('Сверено человеком по синтетическому сценарию');
  const reviewed = page.waitForResponse((response) => response.url().endsWith('/review') && response.request().method() === 'POST');
  await detail.getByRole('button', { name: 'Подтвердить совпадение', exact: true }).click(); const confirmation = await (await reviewed).json();
  expect(confirmation.status).toBe('MATCHED'); expect(confirmation.confirmed_by).toBeTruthy(); await expect(detail).toContainText('Подтвердил пользователь');
  await expect(detail.getByRole('region', { name: 'Решение человека', exact: true })).toContainText('Сверено человеком по синтетическому сценарию');
  const remaining = await (await page.request.get('/api/v1/matching-runs/' + run.id + '/candidates?status=POSSIBLE_MATCH')).json();
  expect(remaining.length).toBeGreaterThan(0);
  const rejectedCandidate = remaining[0];
  await result.getByRole('button', { name: rejectedCandidate.raw_record_a_id + ' ↔ ' + rejectedCandidate.raw_record_b_id, exact: true }).click();
  await detail.getByLabel('Причина подтверждения или отклонения').fill('Проверено: разные сущности, объединять нельзя');
  const rejected = page.waitForResponse((response) => response.url().endsWith('/review') && response.request().method() === 'POST');
  await detail.getByRole('button', { name: 'Отклонить совпадение', exact: true }).click();
  const rejection = await (await rejected).json();
  expect(rejection.status).toBe('NOT_MATCHED');
  expect(rejection.confirmed_by).toBeTruthy();
  await expect(detail.getByRole('region', { name: 'Решение человека', exact: true })).toContainText('Проверено: разные сущности, объединять нельзя');
  await page.getByRole('button', { name: 'Выйти', exact: true }).click(); await signIn(page, 'VIEWER'); await chooseRun(page, run.id);
  await expect(page.getByRole('button', { name: 'Запустить сопоставление', exact: true })).toHaveCount(0);
  const after = await Promise.all(ids.map(async (id) => (await page.request.get('/api/v1/analysis/' + id + '/records')).json())); expect(after).toEqual(before);
  expect((await page.request.get('/api/v1/conflicts')).status()).toBe(200);
});
