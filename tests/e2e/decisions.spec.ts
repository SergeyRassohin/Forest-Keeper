import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
const accounts = JSON.parse(readFileSync(resolve(process.cwd(), '../deploy/local/e2e.json'), 'utf8'));
async function login(page: Page, role: string) {
  await page.goto('/'); await page.getByLabel('Логин', { exact: true }).fill(accounts[role].login);
  await page.getByLabel('Пароль', { exact: true }).fill(accounts[role].password);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Выйти', exact: true })).toBeVisible();
}
async function prepare(page: Page) {
  const headers = { Origin: new URL(page.url()).origin };
  const profiles = await (await page.request.get('/api/v1/analysis/profiles')).json();
  const template = profiles.find((p: { code: string }) => p.code === 'synthetic-material');
  const ids: string[] = [];
  for (const side of ['a', 'b']) {
    const source = await page.request.post('/api/v1/sources', { headers, data: { code: accounts.prefix + '_decision_' + randomUUID().slice(0, 8), name: 'Decision test ' + side, source_type: side === 'a' ? 'FILE' : 'ONE_C' } });
    expect(source.status()).toBe(201);
    const name = side === 'a' ? 'source-a.csv' : 'onec.xml';
    const imported = await page.request.post('/api/v1/imports', { headers, multipart: { source_id: (await source.json()).id, file: { name, mimeType: side === 'a' ? 'text/csv' : 'application/xml', buffer: readFileSync(resolve(process.cwd(), '../tests/data/conflicts/source-' + side + (side === 'a' ? '.csv' : '.xml'))) } } });
    expect(imported.status()).toBe(201); const batch = await imported.json();
    await expect.poll(async () => (await (await page.request.get('/api/v1/imports/' + batch.id)).json()).status, { timeout: 30000 }).toBe('COMPLETED');
    const normalized = await page.request.post('/api/v1/analysis', { headers, data: { import_batch_ids: [batch.id], template_id: template.id } });
    expect(normalized.status()).toBe(201); const run = await normalized.json(); ids.push(run.id);
    await expect.poll(async () => (await (await page.request.get('/api/v1/analysis/' + run.id)).json()).status, { timeout: 30000 }).toBe('COMPLETED');
  }
  const profilesMatching = await (await page.request.get('/api/v1/matching-profiles')).json();
  const matched = await page.request.post('/api/v1/matching-runs', { headers, data: { analysis_run_ids: ids, profile_id: profilesMatching.find((p: { code: string }) => p.code === 'synthetic-material').id } });
  expect(matched.status()).toBe(201); const matching = await matched.json();
  await expect.poll(async () => (await (await page.request.get('/api/v1/matching-runs/' + matching.id)).json()).status, { timeout: 30000 }).toBe('COMPLETED');
  const generated = await page.request.post('/api/v1/conflict-runs', { headers, data: { matching_run_id: matching.id } });
  expect(generated.status()).toBe(201); const generation = await generated.json();
  await expect.poll(async () => (await (await page.request.get('/api/v1/conflict-runs/' + generation.id)).json()).status, { timeout: 30000 }).toBe('COMPLETED');
  const rows = await (await page.request.get('/api/v1/conflicts?matching_run_id=' + matching.id)).json();
  return { matching: matching.id, conflict: rows.find((r: { conflict_type: string }) => r.conflict_type === 'VALUE_MISMATCH').id };
}
async function open(page: Page, fixture: { matching: string; conflict: string }) {
  await page.getByRole('button', { name: 'Конфликты', exact: true }).click();
  await page.getByRole('combobox', { name: 'Сопоставление для конфликтов', exact: true }).selectOption(fixture.matching);
  await page.getByRole('button', { name: 'Открыть конфликт ' + fixture.conflict, exact: true }).click();
  await expect(page.getByRole('region', { name: 'Карточка конфликта', exact: true })).toContainText('12.5');
}
test('human confirmation receipt refresh correction immutable registry and read-only roles', async ({ page, browser }) => {
  test.setTimeout(180000); await login(page, 'DATA_OWNER'); const fixture = await prepare(page); await open(page, fixture);
  const retrieval = await (await page.request.get('/api/v1/conflicts/' + fixture.conflict + '/similar-decisions')).json();
  expect(retrieval.state).toBe('UNAVAILABLE');
  await expect(page.getByRole('region', { name: 'Похожие прошлые решения', exact: true })).toContainText('Поиск временно недоступен');
  const evidenceBefore = await (await page.request.get('/api/v1/conflicts/' + fixture.conflict)).json();
  await page.getByRole('button', { name: 'Начать рассмотрение', exact: true }).click();
  await page.getByRole('radio', { name: /^Источник A:/ }).check();
  await page.getByLabel('Обоснование решения', { exact: true }).fill('Сверен документ поставщика. <script>literal</script>');
  await page.getByRole('button', { name: 'Проверить перед сохранением', exact: true }).click();
  const dialog = page.getByRole('dialog'); await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Сохранить решение', exact: true })).toBeFocused();
  await page.keyboard.press('Escape'); await expect(dialog).not.toBeVisible();
  await page.getByRole('button', { name: 'Проверить перед сохранением', exact: true }).click();
  const saved = page.waitForResponse((r) => r.url().endsWith('/decisions') && r.request().method() === 'POST');
  await dialog.getByRole('button', { name: 'Сохранить решение', exact: true }).click();
  const receipt = await (await saved).json(); await expect(page.getByText('Решение сохранено', { exact: true })).toBeVisible();
  expect(receipt.decision_id).toBeTruthy();
  await page.reload(); await open(page, fixture); await expect(page.getByRole('region', { name: 'Рассмотрение конфликта', exact: true })).toContainText(receipt.decision_id);
  await page.getByRole('button', { name: 'Пересмотреть решение', exact: true }).click();
  await page.getByRole('radio', { name: 'Указать другое значение', exact: true }).check();
  await page.getByRole('textbox', { name: /^Подтверждённое значение/ }).fill('13,25');
  await page.getByLabel('Обоснование решения', { exact: true }).fill('Уточнено по новому подтверждению человека.');
  await page.getByRole('button', { name: 'Проверить перед сохранением', exact: true }).click();
  await dialog.getByRole('button', { name: 'Сохранить решение', exact: true }).click();
  await expect(page.getByText('Решение сохранено', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Открыть решение в реестре', exact: true }).click();
  await expect(page.getByRole('main', { name: 'Реестр решений', exact: true })).toContainText('13.25');
  const history = await (await page.request.get('/api/v1/conflicts/' + fixture.conflict + '/decisions')).json();
  expect(history.map((r: { status: string }) => r.status)).toEqual(['SUPERSEDED', 'ACTIVE']);
  expect(history[1].supersedes_decision_id).toBe(receipt.decision_id);
  const after = await (await page.request.get('/api/v1/conflicts/' + fixture.conflict)).json();
  expect(after.values_snapshot).toEqual(evidenceBefore.values_snapshot); expect(after.basis).toEqual(evidenceBefore.basis);
  for (const role of ['VIEWER', 'ADMIN']) {
    const session = await browser.newContext({ baseURL: new URL(page.url()).origin, ignoreHTTPSErrors: true }); const reader = await session.newPage();
    await login(reader, role); await open(reader, fixture);
    await expect(reader.getByRole('button', { name: 'Пересмотреть решение', exact: true })).toHaveCount(0);
    const denied = await reader.request.post('/api/v1/conflicts/' + fixture.conflict + '/decisions', { headers: { Origin: new URL(page.url()).origin }, data: { context_version: 'a'.repeat(64), idempotency_key: randomUUID(), decision_type: 'DEFERRED', reason: 'forbidden', confirmed: true } });
    expect(denied.status()).toBe(403); await session.close();
  }
});

test('two reviewer browser sessions keep the same evidence token and only one decision wins', async ({ page, browser }) => {
  test.setTimeout(120000); await login(page, 'DATA_OWNER'); const fixture = await prepare(page);
  const origin = new URL(page.url()).origin;
  const review = await (await page.request.get('/api/v1/conflicts/' + fixture.conflict + '/review-context')).json();
  const started = await page.request.post('/api/v1/conflicts/' + fixture.conflict + '/review', { headers: { Origin: origin }, data: { context_version: review.context_version } });
  expect(started.status()).toBe(200);
  const sessions = await Promise.all([0, 1].map(() => browser.newContext({ baseURL: origin, ignoreHTTPSErrors: true })));
  try {
    const reviewers = await Promise.all(sessions.map((session) => session.newPage()));
    await Promise.all(reviewers.map(async (reviewer, index) => {
      await login(reviewer, 'REVIEWER'); await open(reviewer, fixture);
      await reviewer.getByRole('button', { name: 'Начать рассмотрение', exact: true }).click();
      await reviewer.getByRole('radio', { name: index ? /^Источник B:/ : /^Источник A:/ }).check();
      await reviewer.getByLabel('Обоснование решения', { exact: true }).fill('Независимая проверка эксперта ' + index);
      await reviewer.getByRole('button', { name: 'Проверить перед сохранением', exact: true }).click();
    }));
    const received = reviewers.map((reviewer) => reviewer.waitForResponse((r) => r.url().endsWith('/decisions') && r.request().method() === 'POST'));
    await Promise.all(reviewers.map((reviewer) => reviewer.getByRole('dialog').getByRole('button', { name: 'Сохранить решение', exact: true }).click()));
    const responses = await Promise.all(received);
    expect(responses.map((r) => r.status()).sort()).toEqual([201, 409]);
    const loser = reviewers[responses.findIndex((r) => r.status() === 409)];
    await expect(loser.getByRole('alert')).toContainText('Контекст изменился');
    await expect(loser.getByLabel('Обоснование решения', { exact: true })).toHaveCount(0);
    const history = await (await page.request.get('/api/v1/conflicts/' + fixture.conflict + '/decisions')).json();
    expect(history).toHaveLength(1); expect(history[0].status).toBe('ACTIVE');
  } finally { await Promise.all(sessions.map((session) => session.close())); }
});
