import { test, expect } from '@playwright/test';

test('system theme is applied before React, explicit choice persists and switching preserves login input', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  let release = () => {};
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/assets/*.js', async route => { await held; await route.continue(); });
  try {
    await page.goto('/', { waitUntil: 'commit' });
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await expect(page.locator('#root')).toBeEmpty();
  } finally { release(); }
  await page.unrouteAll({ behavior: 'wait' });
  await expect(page.getByRole('heading', { name: 'Вход в Forest Keeper' })).toBeVisible();
  await page.getByLabel('Логин', { exact: true }).fill('draft-login');
  await page.getByLabel('Пароль', { exact: true }).fill('synthetic-unsent-input');
  await page.getByRole('button', { name: 'Светлая тема', exact: true }).click();
  await expect(page.getByLabel('Логин', { exact: true })).toHaveValue('draft-login');
  await expect(page.getByLabel('Пароль', { exact: true })).toHaveValue('synthetic-unsent-input');
  await expect(page.getByRole('button', { name: 'Светлая тема', exact: true })).toHaveAttribute('aria-pressed', 'true');
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual(['fk-theme']);
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.getByRole('button', { name: 'Светлая тема', exact: true })).toHaveAttribute('aria-pressed', 'true');
});

test('blocked browser storage leaves a usable session theme and login form', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.emulateMedia({ colorScheme: 'light' });
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('Storage blocked', 'SecurityError'); } });
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Вход в Forest Keeper' })).toBeVisible();
  await page.getByRole('button', { name: 'Тёмная тема', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByLabel('Логин', { exact: true }).fill('session-draft');
  await page.getByRole('button', { name: 'Светлая тема', exact: true }).click();
  await expect(page.getByLabel('Логин', { exact: true })).toHaveValue('session-draft');
  expect(errors).toEqual([]);
});
