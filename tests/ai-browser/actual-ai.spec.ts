import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const fixture = JSON.parse(readFileSync(process.env.FK_AI_BROWSER_FIXTURE ?? '/tmp/fk-stage9-ai-browser-fixture/fixture.json', 'utf8'));
if (fixture.kind !== 'owned-stage9-synthetic-browser-fixture-v1' || fixture.ready !== true) throw new Error('Prepared owned fixture required');
const output = process.env.FK_AI_BROWSER_OUTPUT ?? '/tmp/fk-stage9-ai-browser-screens';
const project = process.env.FK_AI_BROWSER_RUNTIME_PROJECT;
if (!project || !/^[a-z0-9][a-z0-9_-]{0,62}$/.test(project)) throw new Error('Explicit owned model project required');
const models = ['llm', 'embedding'].map(kind => `${project}-fk-ai-${kind}-1`);
for (const name of models) {
  const owner = execFileSync('docker', ['inspect', '--format', '{{index .Config.Labels "com.docker.compose.project"}}', name], { encoding: 'utf8' }).trim();
  if (owner !== project) throw new Error('Model container ownership mismatch');
}
const report: Record<string, unknown> = { kind: 'own-synthetic-actual-qwen-browser-not-gold', passed: false, captures: [], accessibility: [], responsive: [] };
async function open(page: Page, caseId: string, matchingId: string) {
  await page.getByRole('button', { name: 'Конфликты', exact: true }).click();
  await page.getByRole('combobox', { name: 'Сопоставление для конфликтов', exact: true }).selectOption(matchingId);
  await page.getByRole('button', { name: 'Открыть конфликт ' + caseId, exact: true }).click();
  await page.getByRole('button', { name: 'Начать рассмотрение', exact: true }).click();
  await expect(page.getByLabel('Обоснование решения', { exact: true })).toBeVisible();
}
async function chooseAndExplain(page: Page, reason: string) {
  await page.getByRole('radio', { name: /^Источник [AB]:.*12\.5 kg$/ }).check();
  await page.getByLabel('Обоснование решения', { exact: true }).fill(reason);
}
async function save(page: Page) {
  const response = page.waitForResponse(r => r.url().endsWith('/decisions') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Проверить перед сохранением', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Сохранить решение', exact: true }).click();
  expect((await response).status()).toBe(201);
  await expect(page.getByText('Решение сохранено', { exact: true })).toBeVisible();
}
async function capture(page: Page, label: string) {
  const panel = page.getByRole('region', { name: 'Локальное AI-объяснение', exact: true });
  for (const theme of ['light', 'dark']) {
    await page.getByRole('button', { name: theme === 'dark' ? 'Тёмная тема' : 'Светлая тема', exact: true }).click();
    for (const width of [1920, 1440, 1280, 1024, 390]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
      const dimensions = await page.evaluate(() => ({ width: innerWidth, document: document.documentElement.scrollWidth }));
      expect(dimensions.document).toBeLessThanOrEqual(dimensions.width + 1);
      (report.responsive as unknown[]).push({ label, theme, ...dimensions, passed: true });
      if (![1440, 390].includes(width)) continue;
      const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
      expect(axe.violations).toEqual([]);
      (report.accessibility as unknown[]).push({ label, theme, width, violations: [] });
      await panel.scrollIntoViewIfNeeded();
      const file = `${label}-${theme}-${width}.png`;
      await page.screenshot({ path: resolve(output, file), animations: 'disabled' });
      (report.captures as unknown[]).push({ file, theme, width, sha256: createHash('sha256').update(readFileSync(resolve(output, file))).digest('hex') });
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Светлая тема', exact: true }).click();
}

test('actual local Qwen explanation, draft/theme/evidence and manual decision with both models stopped', async ({ page }) => {
  mkdirSync(output, { recursive: true });
  let automaticDecisions = 0;
  const countWrites = (request: { url(): string; method(): string }) => { if (request.url().endsWith('/decisions') && request.method() === 'POST') automaticDecisions++; };
  try {
    await page.goto('/');
    await page.getByLabel('Логин', { exact: true }).fill(fixture.login);
    await page.getByLabel('Пароль', { exact: true }).fill(fixture.password);
    await page.getByRole('button', { name: 'Войти', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Выйти', exact: true })).toBeVisible();
    await open(page, fixture.case_id, fixture.matching_id);
    const reason = 'Проверил собственный исходный документ: масса12.5kg. Решение подтверждаю лично.';
    await chooseAndExplain(page, reason);
    await expect(page.getByRole('region', { name: 'Рекомендация Forest Keeper', exact: true })).toContainText('Есть обоснованное предложение', { timeout: 45000 });
    const panel = page.getByRole('region', { name: 'Локальное AI-объяснение', exact: true });
    let completed: { state: string; model: { production_accepted: boolean }; clauses: { decision_ids: string[] }[] } | undefined;
    page.on('response', async response => {
      if (response.url().includes('/ai-explanations/') && response.request().method() === 'GET' && response.ok()) {
        const value = await response.json().catch(() => null);
        if (value?.state === 'COMPLETED') completed = value;
      }
    });
    page.on('request', countWrites);
    await panel.getByRole('button', { name: 'Получить AI-объяснение', exact: true }).click();
    await expect(panel).toContainText('Демонстрационный режим локальной Qwen', { timeout: 150000 });
    await expect.poll(() => completed?.state).toBe('COMPLETED');
    expect(completed?.model.production_accepted).toBe(false);
    const citations = completed!.clauses.flatMap(row => row.decision_ids);
    expect(citations).toHaveLength(1);
    expect(fixture.precedents).toContain(citations[0]);
    await expect(page.getByLabel('Обоснование решения', { exact: true })).toHaveValue(reason);
    await expect(page.getByRole('radio', { name: /^Источник [AB]:.*12\.5 kg$/ })).toBeChecked();
    await capture(page, 'real-qwen-explanation');
    await expect(page.getByLabel('Обоснование решения', { exact: true })).toHaveValue(reason);
    expect(automaticDecisions).toBe(0);
    page.off('request', countWrites);
    await panel.getByRole('button', { name: 'Посмотреть подтверждённое решение', exact: true }).click();
    await expect(page.getByRole('main', { name: 'Реестр решений', exact: true })).toBeVisible();
    expect((await page.request.get('/api/v1/decisions/' + citations[0])).status()).toBe(200);
    await page.getByRole('button', { name: 'Вернуться к текущему конфликту', exact: true }).click();
    await page.getByRole('button', { name: 'Начать рассмотрение', exact: true }).click();
    await chooseAndExplain(page, reason);
    await save(page);
    report.actual_model = completed?.model;
    report.verified_case_id = fixture.case_id; report.verified_cited_decision_ids = citations;
    report.citations_valid = true; report.no_ai_business_writes = true;
    report.draft_and_theme_preserved = true; report.explicit_human_decision = true;

    execFileSync('docker', ['stop', '--time', '10', ...models], { stdio: 'pipe' });
    await open(page, fixture.fallback_case_id, fixture.fallback_matching_id);
    const fallback = 'Обе модели выключены. Самостоятельно сверил документ и сохраняю решение.';
    await chooseAndExplain(page, fallback);
    await panel.getByRole('button', { name: 'Получить AI-объяснение', exact: true }).click();
    await expect(panel).toContainText(/Обоснованное AI-объяснение недоступно|AI-объяснение сейчас недоступно/, { timeout: 30000 });
    await expect(page.getByLabel('Обоснование решения', { exact: true })).toHaveValue(fallback);
    await capture(page, 'both-models-stopped');
    await expect(page.getByLabel('Обоснование решения', { exact: true })).toHaveValue(fallback);
    await save(page);
    report.both_models_stopped_manual_decision = true; report.flow_passed = true;
  } finally {
    // Only these explicitly verified owned model containers; no pulls/volume changes.
    try {
      execFileSync('docker', ['start', ...models], { stdio: 'pipe' });
      await expect.poll(() => models.map(name => execFileSync('docker', ['inspect', '--format', '{{.State.Health.Status}}', name], { encoding: 'utf8', timeout: 5000 }).trim()), { timeout: 180000, intervals: [1000, 2000, 5000] }).toEqual(['healthy', 'healthy']);
      report.models_restored_healthy = true;
    } finally {
      report.passed = report.flow_passed === true && report.models_restored_healthy === true;
      writeFileSync(resolve(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
    }
  }
});
