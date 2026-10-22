import { test, expect, type Page, type Locator } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';

const root = resolve(process.cwd(), '..');
const accounts = JSON.parse(readFileSync(resolve(root, 'deploy/local/e2e.json'), 'utf8'));
const output = process.env.FK_GALLERY_OUTPUT;
const report: { captures: Record<string, unknown>[]; accessibility: Record<string, unknown>[]; responsive: Record<string, unknown>[] } = { captures: [], accessibility: [], responsive: [] };
const viewports = [{ width: 1920, height: 1080 }, { width: 1440, height: 900 }, { width: 1280, height: 800 }, { width: 1024, height: 768 }, { width: 390, height: 844 }];

async function signIn(page: Page, role = 'ADMIN') {
  await page.goto('/');
  await page.getByLabel('Логин', { exact: true }).fill(accounts[role].login);
  await page.getByLabel('Пароль', { exact: true }).fill(accounts[role].password);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Выйти', exact: true })).toBeVisible();
}
async function signOut(page: Page) {
  const response = page.waitForResponse((r) => r.url().endsWith('/api/v1/auth/logout') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Выйти', exact: true }).click();
  expect((await response).ok()).toBeTruthy();
  await expect(page.getByLabel('Логин', { exact: true })).toBeVisible();
}
async function capture(page: Page, file: string, title: string, description: string, target?: Locator) {
  if (!output) throw new Error('FK_GALLERY_OUTPUT is required; use capture-ui-gallery.sh');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.evaluate(() => document.fonts.ready);
  await page.setViewportSize({ width: 1440, height: 900 });
  const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  report.accessibility.push({ screen: file, violations: accessibility.violations.map(({ id, impact, description, nodes }) => ({ id, impact, description, targets: nodes.map((n) => n.target) })) });
  expect(accessibility.violations, file + ' accessibility').toEqual([]);
  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    const dimensions = await page.evaluate(() => ({ viewport: window.innerWidth, document: document.documentElement.scrollWidth }));
    report.responsive.push({ screen: file, ...viewport, ...dimensions, passed: dimensions.document <= dimensions.viewport + 1 });
    expect(dimensions.document, file + ' body overflow at ' + viewport.width).toBeLessThanOrEqual(dimensions.viewport + 1);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  if (target) {
    await expect(target).toBeVisible();
    await target.evaluate((element) => element.scrollIntoView({ block: 'start', inline: 'nearest' }));
  }
  else await page.evaluate(() => window.scrollTo(0, 0));
  await page.mouse.move(0, 0);
  const path = resolve(output, file + '.png');
  await page.screenshot({ path, fullPage: false, animations: 'disabled' });
  report.captures.push({ file: file + '.png', title, description, feature_status: 'Реализовано · Stage 0–5', viewport: { width: 1440, height: 900 }, sha256: createHash('sha256').update(readFileSync(path)).digest('hex') });
}
async function importSource(page: Page, side: 'a' | 'b') {
  await page.getByRole('button', { name: 'Импорт данных', exact: true }).click();
  const details = page.locator('details').filter({ hasText: 'Добавить источник' });
  if (!(await details.evaluate((e) => (e as HTMLDetailsElement).open))) await details.locator('summary').click();
  await page.getByLabel('Название источника', { exact: true }).fill(side === 'a' ? 'Excel · Каталог снабжения' : '1С · Номенклатура');
  await page.getByLabel('Код источника', { exact: true }).fill(accounts.prefix + '_gallery_' + side);
  await page.getByRole('combobox', { name: 'Тип источника', exact: true }).selectOption(side === 'a' ? 'FILE' : 'ONE_C');
  await page.getByRole('button', { name: 'Создать источник', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Источник создан' })).toBeVisible();
  await details.locator('summary').click();
  await page.getByLabel('Исходный файл', { exact: true }).setInputFiles(resolve(root, 'tests/data/ui-gallery/' + (side === 'a' ? 'catalog.csv' : 'onec.xml')));
  const uploaded = page.waitForResponse((r) => r.url().endsWith('/api/v1/imports') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Загрузить', exact: true }).click();
  const batch = await (await uploaded).json();
  const card = page.getByRole('region', { name: 'Карточка импорта', exact: true });
  await expect(card).toContainText('Завершён', { timeout: 30000 });
  if (side === 'a') {
    await capture(page, '04-import-detail', 'Оригинал и записи', 'Сохранённый файл, исходные поля и происхождение каждой записи. Данные в источнике не изменяются.', card);
    await capture(page, '18-raw-records', 'Исходные записи и их поля', 'Структурированный просмотр значений без стены JSON. Видны ключ, позиция и исходные поля.', page.getByRole('heading', { name: 'Исходные записи', exact: true }));
  }
  const normalization = page.getByRole('region', { name: 'Нормализация', exact: true });
  const started = page.waitForResponse((r) => r.url().endsWith('/api/v1/analysis') && r.request().method() === 'POST');
  await normalization.getByRole('button', { name: 'Нормализовать пакет', exact: true }).click();
  const run = await (await started).json();
  await expect(normalization.getByRole('status')).toContainText('Нормализация завершена', { timeout: 30000 });
  if (side === 'a') {
    await normalization.locator('.normalization-record summary').first().click();
    await capture(page, '05-normalization', 'Исходное → сопоставимое', 'Масса приводится к единой единице; исходное значение, качество и правило остаются доступными. Нормализация не объявляет значение истиной.', normalization);
  }
  return { analysis: run.id as string, batch: batch.id as string };
}

test('real product gallery, WCAG baseline and responsive Stage 1–5 path', async ({ page }) => {
  test.setTimeout(300000);
  page.setDefaultTimeout(30000);
  if (process.env.FK_CAPTURE_UI !== '1' || !output) throw new Error('Explicit gallery opt-in is required');
  mkdirSync(output, { recursive: true });
  const bundles: { file: string; sha256: string }[] = [];
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  for (const url of await page.locator('script[src], link[rel=stylesheet]').evaluateAll((nodes) => nodes.map((e) => e.getAttribute('src') ?? e.getAttribute('href')).filter((value): value is string => !!value && value.startsWith('/assets/')))) {
    const response = await page.request.get(url);
    expect(response.status()).toBe(200);
    const sha256 = createHash('sha256').update(await response.body()).digest('hex');
    expect(sha256).toBe(createHash('sha256').update(readFileSync(resolve(root, 'frontend/dist', url.slice(1)))).digest('hex'));
    bundles.push({ file: url, sha256 });
  }
  expect(bundles.length).toBeGreaterThanOrEqual(2);
  for (const asset of ['forest-keeper.svg', 'forest-dark.jpg']) {
    const response = await page.request.get('/brand/' + asset);
    expect(response.status()).toBe(200);
    expect(createHash('sha256').update(await response.body()).digest('hex')).toBe(createHash('sha256').update(readFileSync(resolve(root, 'frontend/public/brand', asset))).digest('hex'));
  }
  await expect(page.getByRole('heading', { name: 'Вход в Forest Keeper' })).toBeVisible();
  await capture(page, '01-login', 'Вход в рабочее пространство', 'Защищённая браузерная сессия. Доступ к действиям определяется назначенными ролями.');
  await page.keyboard.press('Tab');
  const focus = await page.locator(':focus').evaluate((e) => ({ outline: getComputedStyle(e).outlineStyle, width: getComputedStyle(e).outlineWidth }));
  expect(focus.outline).not.toBe('none'); expect(focus.width).not.toBe('0px');
  await signIn(page);
  await expect(page.getByText('Сервер готов', { exact: true })).toBeVisible();
  await capture(page, '02-overview', 'Готовность среды', 'Настоящий ответ сервера: состояние API, PostgreSQL и Redis. Здесь нет выдуманных показателей качества данных.');
  await page.getByRole('button', { name: 'Импорт данных', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Импорт данных', exact: true })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'Загружаем' })).toHaveCount(0);
  await capture(page, '03-import', 'Источники и импорт', 'Загрузка CSV, XLSX и XML с сохранением оригинала. Пустая таблица объясняет, с чего начать.');
  const a = await importSource(page, 'a');
  const b = await importSource(page, 'b');
  await page.getByRole('button', { name: 'Сопоставление', exact: true }).click();
  await page.getByRole('combobox', { name: 'Нормализация источника A', exact: true }).selectOption(a.analysis);
  await page.getByRole('combobox', { name: 'Нормализация источника B', exact: true }).selectOption(b.analysis);
  const started = page.waitForResponse((r) => r.url().endsWith('/api/v1/matching-runs') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Запустить сопоставление', exact: true }).click();
  const matching = await (await started).json();
  const result = page.getByRole('region', { name: 'Результат сопоставления', exact: true });
  await expect(result.getByRole('status')).toContainText('Сопоставление завершено', { timeout: 30000 });
  await capture(page, '06-matching', 'Какие записи относятся к одной сущности', 'Отдельно показаны совпадения, отклонённые пары и кандидаты для проверки. Оценка похожести сама по себе не подтверждает идентичность.', result);
  const candidates = await (await page.request.get('/api/v1/matching-runs/' + matching.id + '/candidates?status=MATCHED&limit=100')).json();
  let selected: { id: string; raw_record_a_id: string; raw_record_b_id: string } | undefined;
  for (const candidate of candidates) {
    const card = await (await page.request.get('/api/v1/match-candidates/' + candidate.id)).json();
    if (card.records.every((r: { source_record_key: string }) => r.source_record_key === 'MAT-001')) selected = candidate;
  }
  expect(selected).toBeTruthy();
  await result.getByRole('button', { name: 'Сравнить записи ' + selected!.raw_record_a_id + ' ↔ ' + selected!.raw_record_b_id, exact: true }).click();
  await expect(page.getByRole('region', { name: 'Основание сопоставления', exact: true })).toBeVisible();
  await capture(page, '07-match-detail', 'Основания совпадения', 'Обе исходные записи, нормализованные значения и вклад признаков доступны рядом. Подтверждение идентичности не выбирает правильную массу.', page.getByRole('region', { name: 'Основание сопоставления', exact: true }));
  await page.getByRole('button', { name: 'Открыть конфликты сопоставления', exact: true }).click();
  const generated = page.waitForResponse((r) => r.url().endsWith('/api/v1/conflict-runs') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Проверить конфликты', exact: true }).click();
  const execution = await (await generated).json();
  await expect(page.getByRole('status').filter({ hasText: execution.id })).toContainText('COMPLETED', { timeout: 30000 });
  await capture(page, '08-conflicts', 'Расхождения значений', 'Список объяснимых конфликтов подтверждённых пар. Человеческие подписи сопровождают технические типы и статусы.');
  const conflicts = await (await page.request.get('/api/v1/conflicts?matching_run_id=' + matching.id)).json();
  const mismatch = conflicts.find((r: { conflict_type: string }) => r.conflict_type === 'VALUE_MISMATCH');
  expect(mismatch).toBeTruthy();
  await page.getByRole('button', { name: 'Открыть конфликт ' + mismatch.id, exact: true }).click();
  const conflict = page.getByRole('region', { name: 'Карточка конфликта', exact: true });
  await expect(conflict).toContainText('12.4');
  await capture(page, '09-conflict-detail', 'Что не совпало и откуда взялись значения', '12500 g и 12.4 kg сравниваются как 12.5 и 12.4 kg. Видны два источника и контекст нормализации. Решение человека ещё не принято.', conflict);
  expect(await page.getByRole('button', { name: /Принять решение|Выбрать значение|Исправить|Записать в систему|Применить рекомендацию/ }).count()).toBe(0);
  await conflict.locator('.source-card details > summary').first().click();
  await capture(page, '17-provenance', 'От результата к исходной записи', 'По запросу раскрываются файл, контрольная сумма, позиция исходной записи и правило нормализации. Это реальные сохранённые сведения, а не макет.', conflict.locator('.source-card').first());
  await page.getByRole('combobox', { name: 'Тип конфликта', exact: true }).selectOption('RULE_VIOLATION');
  await expect(page.getByRole('heading', { name: 'Конфликты не найдены', exact: true })).toBeVisible();
  await capture(page, '10-empty', 'Понятное пустое состояние', 'Результат фильтра не подменяется вымышленными данными. RULE_VIOLATION пока не генерируется без утверждённого источника правил.');
  await page.getByRole('button', { name: 'Пользователи', exact: true }).click();
  await expect(page.getByRole('listitem')).not.toHaveCount(0);
  await capture(page, '11-users', 'Пользователи и роли', 'Администратор управляет доступом. Роль ADMIN сама по себе не даёт полномочий подтверждать совпадения или принимать бизнес-решения.');
  await signOut(page);
  await signIn(page, 'REVIEWER');
  await page.getByRole('button', { name: 'Сопоставление', exact: true }).click();
  await page.getByRole('combobox', { name: 'Запуск сопоставления', exact: true }).selectOption(matching.id);
  await page.getByRole('combobox', { name: 'Статус кандидата', exact: true }).selectOption('POSSIBLE_MATCH');
  const pending = await (await page.request.get('/api/v1/matching-runs/' + matching.id + '/candidates?status=POSSIBLE_MATCH')).json();
  expect(pending.length).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Сравнить записи ' + pending[0].raw_record_a_id + ' ↔ ' + pending[0].raw_record_b_id, exact: true }).click();
  await expect(page.getByRole('button', { name: 'Подтвердить совпадение', exact: true })).toBeVisible();
  await capture(page, '12-matching-review', 'Проверка идентичности экспертом', 'Уже существующий matching review требует объяснения. Это проверка того, что записи относятся к одной сущности, а не разрешение конфликта значений.', page.locator('section[aria-label="Основание сопоставления"] form'));
  await signOut(page); await signIn(page, 'VIEWER');
  await page.getByRole('button', { name: 'Конфликты', exact: true }).click();
  await page.getByRole('combobox', { name: 'Сопоставление для конфликтов', exact: true }).selectOption(matching.id);
  await expect(page.getByRole('button', { name: 'Проверить конфликты', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Пользователи', exact: true })).toHaveCount(0);
  await capture(page, '13-viewer', 'Просмотр без полномочий на изменение', 'VIEWER видит разрешённые результаты и их основания. Запуск обработки и управление пользователями не отображаются.');
  await signOut(page); await signIn(page, 'NO_ROLES');
  await expect(page.getByRole('heading', { name: 'Доступ не назначен', exact: true })).toBeVisible();
  await capture(page, '14-permission', 'Роль ещё не назначена', 'Понятный следующий шаг вместо пустого экрана. Авторизация и фактические разрешения проверяются сервером.');
  await signOut(page);
  let releaseSession: () => void = () => {};
  const heldSession = new Promise<void>((resolveRequest) => { releaseSession = resolveRequest; });
  await page.route('**/api/v1/auth/me', async (route) => { await heldSession; await route.continue(); });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Проверяем сессию…', exact: true })).toBeVisible();
  await capture(page, '15-loading', 'Выполнение запроса', 'Настоящее состояние ожидания ответа; для демонстрации ответ намеренно задержан тестом.', page.getByRole('heading', { name: 'Проверяем сессию…', exact: true }));
  releaseSession();
  await page.unroute('**/api/v1/auth/me');
  await expect(page.getByRole('heading', { name: 'Вход в Forest Keeper' })).toBeVisible();
  await page.route('**/api/v1/auth/login', (route) => route.abort());
  await page.getByLabel('Логин', { exact: true }).fill(accounts.VIEWER.login);
  await page.getByLabel('Пароль', { exact: true }).fill(accounts.VIEWER.password);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Не удалось подключиться');
  await expect(page.getByLabel('Пароль', { exact: true })).toHaveValue('');
  await capture(page, '16-error', 'Восстановление после ошибки', 'Симуляция потери соединения: читаемое сообщение, очищенный пароль и возможность повторить попытку.');
  await page.unroute('**/api/v1/auth/login');
  expect(errors).toEqual([]);
  writeFileSync(resolve(output, 'manifest.json'), JSON.stringify({ captured_at: new Date().toISOString(), source_commit: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(), source_tree: execFileSync('git', ['rev-parse', 'HEAD:frontend/src'], { cwd: root, encoding: 'utf8' }).trim(), brand_assets: ['forest-keeper.svg', 'forest-dark.jpg'].map((file) => ({ file, sha256: createHash('sha256').update(readFileSync(resolve(root, 'frontend/public/brand', file))).digest('hex') })), worktree_dirty: execFileSync('git', ['status', '--porcelain'], { cwd: root, encoding: 'utf8' }).trim().length > 0, images: { frontend: process.env.FK_GALLERY_FRONTEND_IMAGE_ID, backend: process.env.FK_GALLERY_BACKEND_IMAGE_ID }, served_bundles: bundles, capture: 'Real HTTPS Web Client and backend with owned synthetic data; no generated/mock product screenshots', locale: 'ru-RU', timezone: 'Europe/Moscow', ...report }, null, 2));
});
