# Готовность к внешней проверке — 24 октября 2026

**Актуально на 23 октября 2026:** Stage 0–6 приняты в `main` через PR #26 (merge `0ce2a14304d0cf28fcf90ec9cd3d6c23601ec852`, exact CI 39947944543 SUCCESS). Stage 7 Similar Decision Retrieval реализуется в отдельной ветке `codex/stage7-similar-decisions` по issue #27. Production embedding provider отключён; синтетический test provider не доказывает промышленное качество. Recommendation Engine, AI/LLM и write-back отсутствуют. #18/#20 остаются открытыми.

Состояние 23 октября 2026: `main` принял Stage 0–6 через PR #26; Stage 7 проверяется в отдельной ветке `codex/stage7-similar-decisions`. Цель — самостоятельная проверка человеком, впервые увидевшим продукт, по [Quick Start](external-review-quickstart.md). Исходные требования: [#18](https://github.com/SergeyRassohin/Forest-Keeper/issues/18). Описание целевого поведения не заменяет работающую функцию.

| Проверка | Состояние main | Что предъявить для полной приёмки |
| --- | --- | --- |
| Clone → setup → первый вход | Реализовано; инструкция исправлена | Отчёт fresh clone на конкретном SHA |
| Два источника, импорт CSV/XLSX/XML, raw/provenance | Этап 2 принят | Проверка собственного файла и открытого примера |
| Нормализация и история правил | Этап 3 принят; только явные профили | Подходящий mapping, исходные/нормализованные значения |
| Matching/evidence | Этап 4 принят в main; независимый retest и CI merge commit PASS | Промышленный pilot domain и проверка реальных файлов |
| Conflict Engine | Этап 5 принят в main, независимый retest и merge CI PASS | Реальные Conflict ID/Basis/provenance и подтверждение сохранности после restart |
| Human Review + Decision Registry | Stage 6 принят в main через PR #26 | Сохранённый Decision, actor/reason/context и immutable history |
| Restart с сохранением Decision | Stage 6 PASS; merge CI main SUCCESS | Проверка того же ID после restart без удаления volumes |
| Similar Decision / recommendation | Stage 7 retrieval в отдельной ветке; production provider/recommendation BLOCKED | Следующий похожий кейс с реальной ссылкой на прошлый Decision |
| Pinned Qwen artifacts | Manifest и lock проверяются; есть downloader | Полная локальная SHA-256 проверка файлов |
| LLM/embedding runtime + model-info | BLOCKED: нет поддерживаемого запуска | Точные ID/revisions; inference и 1024 dimensions smoke |
| AI evidence / offline / LLM failure | BLOCKED: нет интеграции | Только реальные evidence IDs; офлайн-тест; работа истории без LLM |

**Итог: полная внешняя приёмка MVP пока BLOCKED.** Можно проводить техническую проверку реализованных этапов, честно отмечая границу. Human Review/Decision Registry приняты в main; Stage 7 добавляет тестовый retrieval. Production semantic provider/recommendation/AI полного MVP ещё отсутствуют. Эта документация не закрывает #18.

Stage 4: [текущий отчёт и DoD](../testing/reports/stage4-matching-acceptance-2026-10-21.md). Локальные проверки, gold, 100k capacity и restart выполнены; [отдельный independent runtime/security retest](../testing/reports/stage4-matching-independent-2026-10-21.md) PASS без блокирующих замечаний, повторены 619 тестов и все четыре capacity профиля. Владелец принял HEAD `f44e01e` и разрешил merge; main merge `bea0d55c92540744657feac863084cde131a7f43`, [CI — SUCCESS](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39595762080). Шаг 1 / Stage 4 из #20 завершён.

Stage 5: подробное ТЗ, границы, benchmark, migration, browser E2E, recovery и merge gate зафиксированы в [issue #21](https://github.com/SergeyRassohin/Forest-Keeper/issues/21). PR #22 принят и объединён после отдельного разрешения; merge gate завершён.

## Согласованные правила

- Срок: суббота, 24 октября 2026 (контекст пользователя: Europe/Moscow).
- Разрешено использовать открытые данные с проверенным источником и условиями использования. Они служат демонстрацией; первый промышленный pilot domain ими не определяется.
- Fuzzy/weighted similarity не даёт автоматического MATCHED. Нечёткие пары идут на ручную проверку. Автоматическое подтверждение — только по согласованным однозначным точным ключам без конфликтующих strong signals.
- Raw и provenance неизменяемы. Источник не получает write-back. ADMIN не наследует бизнес-права. AI не является памятью и не изменяет правила автоматически.
- Stage 5: `Conflict != Decision`. Conflict Engine обнаруживает проблему, но не выбирает «истинное» значение и не создаёт business Decision.
- `RULE_VIOLATION` допускается только по явному versioned rule source; `ANOMALY` — только по воспроизводимому deterministic detector. LLM не является доказательством аномалии.
- Этапы 5+ проходят собственные architecture/quality gates. [Stage gate](../development/stage-gate-checklist-v0.1.md).

## Что должно быть в пакете для проверяющего

1. Точный commit SHA и статус CI этого SHA.
2. README с назначением продукта и честной таблицей функций.
3. Исполняемая инструкция от установки зависимостей до результата, включая первый вход.
4. Небольшие открытые примеры, источник, условия использования, преобразования и ожидаемые результаты.
5. Проверенные model/revision/artifact URLs и зафиксированные контрольные суммы.
6. PASS/FAIL/BLOCKED по каждому шагу; unresolved blocker не заменяется SKIP или зелёным health.
7. Независимое ревью и исправления до объявления готовности. Существующие исторические отчёты не выдаются за новое независимое ревью этой правки.
8. Для Stage 5 после реализации: реальный Conflict ID, linked MatchCandidate, raw/normalized/provenance, deterministic Basis и сохранность после restart.

## Stage 5: принят в main — 22 октября 2026

PR #22 объединён владельцем в main: `6235dd6a18f8cbb8aeceac2a7d052f5fca396482`; [CI точного merge commit — SUCCESS](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39768647312). Этап 5 принят; 679 тестов и независимый runtime/security/product-intent retest PASS. Шаг Stage 5 из #20 завершён. Human Review/Decision Registry объединены новым ТЗ #25 в Stage 6; #18/#20 остаются открытыми. Полный MVP #18/#20 остаётся незавершённым.

## Stage 5.1 — отдельная подготовка интерфейса

[Issue #23](https://github.com/SergeyRassohin/Forest-Keeper/issues/23): единый бренд существующих экранов, понятные evidence-карточки и [реальная галерея](../../frontend/public/interface/index.html). Съёмка проверяет WCAG A/AA и desktop 1920/1440/1280/1024, дополнительно narrow390px. [Воспроизведение](../development/ui-brand-guidelines.md), [публикация страницы](../site/interface.md). Исходники внешнего сайта и инструмент публикации в среде отсутствуют; готовая страница в репозитории не является подтверждением обновления внешнего домена.

Stage 5.1 не снимает блокеры Decision/AI полного MVP и не даёт ADMIN бизнес-полномочий. Final HEAD, точный CI и независимый visual/product retest фиксируются в PR перед отдельным разрешением на merge.


[Независимая проверка Stage 5.1](../testing/reports/stage51-brand-independent-2026-10-23.md) завершена 23 октября: приложение/галерея в репозитории PASS, блокирующих замечаний нет. 19 Axe/95 viewport checks и повторные 11 E2E PASS. Внешняя публикация §26.17–18 остаётся BLOCKED / NOT VERIFIED. Это не приёмка отсутствующих Decision/AI.


## Stage 6: принят в main

Human Review/Decision Registry приняты владельцем через PR #26 по #25, с каноническими outcomes, immutable history, независимым retest и зелёным exact merge CI 39947944543. Для проверки используйте [сценарий](../development/human-review.md). Stage 7 retrieval проверяется отдельно; production semantic provider, recommendation и AI по #18/#20 остаются BLOCKED.


Stage 6 runtime: `backend/tests/restart_decisions.py` проверяет собственный проект `fk-stage6`, реальные HTTPS receipt/history, сохранность source/evidence, race 201/409, запись при остановленном Redis и тот же persistent key после restart. [Реализованный workflow](../development/human-review.md). Исторические ограничения публикации Stage 5.1 выше относятся к прежним отчётам; issue #25 явно фиксирует принятие и публикацию владельцем. Галерея Stage 6 сохранена в репозитории; обновление внешнего сайта отдельно не заявляется.
