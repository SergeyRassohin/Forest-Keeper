# Stage 2: синхронизация PR #8 с main — 2026-10-20

Основание: [инструкция в issue #7](https://github.com/SergeyRassohin/Forest-Keeper/issues/7#issuecomment-6289508205).

## Состав изменения

- Ветка Stage 2 `7f0acf98d7da13b6395219bf8d888d4bfae6ef98` объединена с `main` / PR #10 `a07fc20c2cb5dcf4faf55fb99f17ccd7114cece3` обычным merge, история сохранена.
- Четыре конфликта: `.gitignore`, `Settings`, worker, dev Compose. Сохранены обе ignore-записи, file secrets и import settings; recovery перед запуском worker, очередь Stage 2, hostname/TTL и read-only readiness PR #10; общий том оригиналов и healthcheck.
- Production сохраняет file secrets, non-root, read-only rootfs, tmpfs, CPU/RAM/PID limits, capabilities/no-new-privileges, persistence PG/Redis и отдельную конфигурацию. Добавлен необходимый Stage 2 `import_files` volume с UID/GID 10001 и явным storage root. Nginx получил те же upload size/buffering настройки, что dev.
- Loopback wget healthcheck явно использует `-Y off`: иначе в данной managed-среде запрос к 127.0.0.1 уходил в унаследованный proxy и падал, хотя прямой запрос возвращал HTTP 200. Внешний smoke сохраняет проверку доверия TLS.
- Production smoke дополнительно проверяет запись marker backend, чтение worker и сохранение точных байтов после перезапуска.
- Stage 2 business modules, parser/RQ regressions, imports UI и browser scenario совпадают с проверенной веткой. Этап 3 не начат. Worker health module/tests, file-secret tests и CI pipeline PR #10 сохранены без изменений относительно main.

## Среда и локальные результаты

Managed Linux, Python 3.13.16, Docker 28.4.0, системный Chromium через `FK_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium`. Dev volumes сохранены; production smoke использует собственные случайные project/volumes/secrets и удаляет только их.

| Проверка | Результат |
| --- | --- |
| `bash scripts/check.sh` | PASS: 95 backend unit, 13 frontend; Ruff/mypy/lint/build/E2E typecheck |
| `bash scripts/check-sast.sh` | PASS: нет находок Python/TypeScript |
| `bash scripts/check-secrets.sh` | PASS: Git history + tracked tree, без утечек |
| `bash scripts/test-security-gates.sh` | PASS: все 3 unsafe fixtures отвергнуты |
| `bash scripts/check-dependencies.sh` | PASS: pip-audit/npm audit без известных уязвимостей |
| Dev `up --build --wait --wait-timeout 180` | PASS с временным build CA override |
| `bash scripts/check-integration.sh` | PASS: 313 integration + 7 browser E2E; migration 0003 |
| `python scripts/check-production.py --backend-image forest-keeper-backend --frontend-image forest-keeper-frontend` | PASS: HTTPS, file secrets, non-root/read-only/resources, реальное RQ задание, healthy → stale/unhealthy → stopped → restored, PG/Redis/original-byte persistence, отсутствие credential values в inspect/logs |

Итого стандартные suites: **428 passed / 0 failed / 0 skipped**. Pytest deselected обозначает разделение unit/integration, не пропуск тестов. Существующее предупреждение Starlette об httpx не блокирует gate.

Регрессии включают CSV/XLSX/XML/1C XML, duplicate upload и concurrency, partial errors, checksum/raw/provenance/immutability, RBAC, RQ processing/recovery и late enqueue; browser проверяет два импорта и исходные записи, duplicate, partial errors, delayed records response.

Первоначальный plain Docker build без CA завершился TLS-ошибкой прокси. Повтор с существующим `network_ca` BuildKit secret PASS; override находится вне Git. Первый browser run не запустил Chromium из нового Playwright cache (1 API PASS, 6 launch FAIL); повтор с системным Chromium дал 7/7 PASS. Production smoke до исправления proxy healthcheck завершался на nginx health, затем повторён на окончательной конфигурации. Первоначальные сбои не скрыты и не включены в итоговый успешный прогон.

## GitHub acceptance

Финальный SHA, результаты production smoke и ссылки GitHub Actions публикуются в PR #8 после коммита этого отчёта. READY TO MERGE допустим только после зелёного CI на финальном HEAD и проверки mergeable. После merge отдельно проверяется CI merge commit и закрытие issue #7.
