import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const accounts = JSON.parse(readFileSync(resolve(process.cwd(), '../deploy/local/e2e.json'), 'utf8'));
const fixture = (name: string) => resolve(process.cwd(), '../tests/data/import', name);

async function createSource(page: Page, suffix: string, type: string) {
  const detail = page.locator('details').filter({ hasText: 'Добавить источник' });
  if (!(await detail.evaluate((element) => (element as HTMLDetailsElement).open))) await detail.locator('summary').click();
  await page.getByLabel('Название источника', { exact: true }).fill('Источник ' + suffix + ' ' + accounts.prefix);
  await page.getByLabel('Код источника', { exact: true }).fill(accounts.prefix + '_' + suffix);
  await page.getByRole('combobox', { name: 'Тип источника', exact: true }).selectOption(type);
  const pending = page.waitForResponse((response) => response.url().endsWith('/api/v1/sources') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Создать источник', exact: true }).click();
  const created = await (await pending).json();
  await expect(page.getByRole('status')).toContainText('Источник создан');
  return created.id as string;
}

async function upload(page: Page, name: string) {
  await page.getByLabel('Исходный файл', { exact: true }).setInputFiles(fixture(name));
  const pending = page.waitForResponse((response) => response.url().endsWith('/api/v1/imports') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Загрузить', exact: true }).click();
  const response = await pending;
  expect([200, 201]).toContain(response.status());
  const body = await response.json();
  return body as { id: string; duplicate: boolean };
}

test('browser imports two sources, shows raw/provenance, duplicates and partial errors', async ({ page }) => {
  test.setTimeout(120000);
  await page.goto('/');
  await page.getByLabel('Логин', { exact: true }).fill(accounts.ADMIN.login);
  await page.getByLabel('Пароль', { exact: true }).fill(accounts.ADMIN.password);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await page.getByRole('button', { name: 'Импорт данных', exact: true }).click();
  const fileSource = await createSource(page, 'files', 'FILE');
  const first = await upload(page, 'valid.csv');
  const card = page.getByRole('region', { name: 'Карточка импорта' });
  await expect(card).toContainText('Завершён', { timeout: 30000 });
  await expect(card).toContainText('001.2300');
  await expect(card).toContainText('line_start');
  await createSource(page, 'one_c', 'ONE_C');
  const second = await upload(page, 'onec.xml');
  expect(second.id).not.toBe(first.id);
  await expect(card).toContainText('Завершён', { timeout: 30000 });
  await expect(card).toContainText('Справочник.Номенклатура');
  const ownRows = page.getByRole('row').filter({ hasText: accounts.prefix });
  await expect(ownRows.getByRole('button', { name: 'valid.csv', exact: true })).toBeVisible();
  await expect(ownRows.getByRole('button', { name: 'onec.xml', exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: 'Источник', exact: true }).selectOption(fileSource);
  const duplicate = await upload(page, 'valid.csv');
  expect(duplicate.duplicate).toBe(true);
  expect(duplicate.id).toBe(first.id);
  await expect(page.getByRole('status')).toContainText('уже загружен');
  const partial = await upload(page, 'partial.csv');
  await expect(card).toContainText('Завершён с ошибками', { timeout: 30000 });
  await expect(card).toContainText('Количество значений не совпадает с заголовком');
  await expect(card).toContainText('Болт');
  const check = await page.request.get(`/api/v1/imports/${partial.id}`);
  expect((await check.json()).records_failed).toBe(2);
});
