import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

interface Account {
  login: string;
  password: string;
}
const accounts: {
  prefix: string;
  ADMIN: Account;
  VIEWER: Account;
  REVIEWER: Account;
} = JSON.parse(
  readFileSync(resolve(process.cwd(), '../deploy/local/e2e.json'), 'utf8'),
);

async function enter(page: Page, account: Account) {
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Вход в Forest Keeper' }),
  ).toBeVisible();
  await page.getByLabel('Логин', { exact: true }).fill(account.login);
  await page.getByLabel('Пароль', { exact: true }).fill(account.password);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByText('Сервер готов', { exact: true })).toBeVisible();
}

test('web client signs in and reads actual dependency readiness', async ({
  page,
  request,
}) => {
  expect((await request.get('/api/v1/health')).status()).toBe(200);
  expect((await request.get('/api/v1/dashboard')).status()).toBe(401);
  await enter(page, accounts.VIEWER);
  await expect(page.getByText('Доступен', { exact: true })).toHaveCount(3);
  await expect(
    page.getByRole('heading', { name: 'Пользователи', exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await expect(page.getByText('Сервер готов', { exact: true })).toBeVisible();
  expect(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
  ).toBe(0);
});

test('invalid password is rejected and cleared', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Логин', { exact: true }).fill(accounts.VIEWER.login);
  await page.getByLabel('Пароль', { exact: true }).fill('incorrect');
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText(
    'Неверный логин или пароль.',
  );
  await expect(page.getByLabel('Пароль', { exact: true })).toHaveValue('');
});

test('ADMIN creates a reviewer without inheriting business permissions', async ({
  page,
}) => {
  await enter(page, accounts.ADMIN);
  const profile = await (await page.request.get('/api/v1/auth/me')).json();
  expect(profile.permissions).toContain('user.manage');
  expect(profile.permissions).not.toContain('decision.create');
  expect(profile.permissions).not.toContain('match.review');
  expect(profile.permissions).not.toContain('rule.activate');
  await page
    .getByLabel('Логин нового пользователя')
    .fill(accounts.prefix + '_created');
  await page.getByLabel('Имя пользователя').fill('Новый эксперт');
  await page.getByLabel('Начальный пароль').fill(accounts.REVIEWER.password);
  await page.getByRole('checkbox', { name: 'VIEWER', exact: true }).uncheck();
  await page.getByRole('checkbox', { name: 'REVIEWER', exact: true }).check();
  await page
    .getByRole('button', { name: 'Создать пользователя', exact: true })
    .click();
  await expect(
    page.getByRole('listitem').filter({ hasText: 'Новый эксперт' }),
  ).toContainText('REVIEWER');
});

test('logout revokes the session, including its bearer token', async ({
  page,
}) => {
  await enter(page, accounts.REVIEWER);
  const cookie = (await page.context().cookies()).find(
    (item) => item.name === '__Host-fk_session',
  )!;
  expect(cookie.httpOnly).toBe(true);
  expect(cookie.secure).toBe(true);
  await page.getByRole('button', { name: 'Выйти', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Вход в Forest Keeper' }),
  ).toBeVisible();
  const response = await page.request.get('/api/v1/auth/me', {
    headers: { Authorization: 'Bearer ' + cookie.value },
  });
  expect(response.status()).toBe(401);
});
