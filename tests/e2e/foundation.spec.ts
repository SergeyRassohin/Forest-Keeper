import { expect, test } from '@playwright/test';

test('web client reads readiness from the real API', async ({ page, request }) => {
  const health = await request.get('/api/v1/health');
  expect(health.status()).toBe(200);
  expect(await health.json()).toEqual({
    status: 'ok', components: { api: 'ok', database: 'ok', redis: 'ok' },
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Основа для доверия к данным' })).toBeVisible();
  await expect(page.getByText('Сервер готов', { exact: true })).toBeVisible();
  await expect(page.getByText('Доступен', { exact: true })).toHaveCount(3);
  await page.getByRole('button', { name: 'Проверить снова' }).click();
  await expect(page.getByText('Сервер готов', { exact: true })).toBeVisible();
});
