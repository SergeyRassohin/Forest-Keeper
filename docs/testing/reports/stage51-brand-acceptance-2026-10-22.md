# Stage 5.1 — Web UI, бренд и реальные экраны

Дата: 22 октября 2026. Scope: [issue #23](https://github.com/SergeyRassohin/Forest-Keeper/issues/23), отдельная ветка `codex/stage51-brand-ui` от принятого Stage 5/main `6789835`. [Входной architecture/product gate](stage51-entry-gate-2026-10-22.md). Final HEAD и CI конкретного SHA указываются в PR; этот отчёт не утверждает, что ветка уже принята владельцем.

## Что изменилось

Оформлены все существующие экраны: вход, обзор инфраструктуры, источники/импорт, карточка пакета и исходные записи, нормализация, matching history/candidates/detail и существующий review идентичности, conflicts list/detail/provenance, пользователи/роли, VIEWER, отсутствие роли, loading/empty/error/completed. Общие [tokens и правила оформления](../../development/ui-brand-guidelines.md) определяют палитру, типографику, отступы, формы, таблицы, focus и статусы.

Лес и исходный amber-logo взяты с текущего сайта, cream рабочая область отделена от pine sidebar. Основной flow — таблицы и значения; технические hashes/JSON/Basis вторичны и доступны по запросу. Нормализация остаётся в карточке импорта, как в принятом продукте. Users вынесены в стабильную отдельную навигацию.

## Brand consistency / screenshot acceptance

| Проверка | Результат / основание |
| --- | --- |
| Приложение vs текущий сайт | Pine/cream/sage, исходные SVG/фото и serif wordmark согласованы; приложение сохраняет рабочую плотность |
| Приложение vs презентация | Природный мотив, спокойные поверхности, одна палитра и аккуратная hierarchy; будущие функции не изображаются работающими |
| Form/table/card/button/status | Общие tokens и компоненты; статус содержит текст и вторичный enum; UUID не основной заголовок |
| Contrast/focus/labels | Проверяется Axe WCAG2/2.1 A/AA на каждом снятом экране и отдельно независимым browser retest |
| Desktop/narrow | 1920×1080,1440×900,1280×800,1024×768,390×844; таблицы могут прокручиваться локально, page overflow запрещён |
| Evidence | Обе записи и raw/normalized/unit/source видны рядом; provenance и версии сохранены |
| Галерея | Реальный HTTPS Web Client/backend, синтетические CSV/1С XML, автоматический Playwright; PNG не ретушируются |
| Состояния ожидания/ошибки | Настоящий UI с управляемым задержанным/отменённым запросом, подписи честно описывают симуляцию |
| Страница галереи | Статическая `/interface/`, внешняя stylesheet совместима с действующей strict CSP; изображения/manifest локальные |
| Старый публичный домен | Публикация НЕ подтверждена: нет проекта сайта и инструмента публикации. [Готовые файлы и инструкция](../../site/interface.md) |

Исходный сайт проверен по опубликованным HTML/CSS/assets; reference screenshot сделан с отключённым JS и не используется как свидетельство интерактивных функций сайта. Окончательное независимое visual/product заключение фиксируется отдельно, не подменяется этим авторским checklist.

## Проверки и исправленные находки

Команды: `bash scripts/check.sh`, `bash scripts/check-integration.sh`, `bash scripts/check-sast.sh`, `bash scripts/test-security-gates.sh`, `bash scripts/check-dependencies.sh`, `bash scripts/check-secrets.sh`, `python scripts/check-production.py --backend-image … --frontend-image …`, `bash scripts/capture-ui-gallery.sh`.

Backend regression: 437 integration/API PASS, включая неизменённые security/RBAC/business invariants и migration head0006. Существующие11 browser E2E PASS. Frontend34 component tests PASS. Production smoke PASS: две параллельные100MB HTTPS-загрузки с checksum; non-root/read-only/resources; file secrets; настоящий RQ job; worker healthy→unhealthy→stopped→restored; PostgreSQL/Redis сохраняются после restart. SAST/SCA/secrets и отрицательные security fixtures PASS.

В процессе реальной проверки устранены: недоступные brand assets из-за прав файлов в nginx image; устаревшая карточка конфликта после смены фильтра/страницы; ложное «не задано» у omitted long raw value; скрытая ошибка загрузки пользователей в read-only UI; несовпадение visible label и accessible button name; переносы логинов/статусов/чисел; несовместимая inline CSS галереи; кадры, показывавшие форму вместо evidence. Capture сверяет реальные JS/CSS/brand bytes с текущей сборкой и записывает immutable Docker image IDs, source tree, PNG checksums и результаты проверок.

## Architecture / Product Intent Gate

Backend app, migrations, canonical enums, lifecycles, evidence storage, API и XLSX access matrix не менялись. Auth остаётся browser cookie, без bearer-flow. Raw/provenance неизменяемы, normalization не truth. Matching review подтверждает только идентичность; Conflict != Decision. ADMIN не получает бизнес-полномочий, VIEWER не получает кнопок запуска/администрирования. Forest Codex явно не настроен. Нет Stage6 Human Review conflict actions, Decision Registry, similarity/LLM/recommendation/write-back и новых backend business endpoints. Ни исходные данные пользователя, ни default Compose volumes не очищались: gallery/production probe используют собственные disposable projects.

## Ограничения приёмки

Внешняя публикация `/interface/` на историческом домене остаётся **BLOCKED / NOT VERIFIED** до доступа к сайту или публикации владельцем. Пользователь согласился с подготовкой готовой страницы в репозитории; это не подтверждение публичного deployment. Полный DoD §26.17–18 по старому внешнему сайту нельзя объявить PASS. Проверки WCAG — automated baseline, не сертификация; agent review — независимая AI-сессия, не human acceptance или pentest. Merge только после отдельного разрешения владельца, Stage6 не начат.

## Финальная локальная автоматическая проверка

**689 уникальных тестов PASS:**200 backend unit,437 integration/API,34 frontend component,11 HTTPS browser,6 model/artifact utility и1 end-to-end gallery scenario. В галерее18 настоящих PNG,18 Axe WCAG2/2.1 A/AA проверок без нарушений и90 viewport checks PASS. Повторные прогоны исправлений и focused independent tests к этому числу не прибавляются.

Снимки: source commit `b3d4423131dcd4e2c07536e7dc05e742015b8c2d`, frontend/src tree `19d0850606bfd3a3fb341d155cb2633d562cb096`. Точные Docker image IDs и served JS/CSS/brand/PNG SHA-256 сохранены в [manifest](../../../frontend/public/interface/manifest.json). Галерея получена после исправления disabled styles; снимки соответствуют финальному application source. Отдельные последующие documentation/evidence commits не меняют это дерево.
