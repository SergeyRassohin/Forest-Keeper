# Готовность к внешней проверке — 24 октября 2026

Снимок 21 октября 2026; `main` после принятия PR #15 с изменениями PR #19. Цель — самостоятельная проверка человеком, впервые увидевшим продукт, по [Quick Start](external-review-quickstart.md). Исходные требования: [#18](https://github.com/SergeyRassohin/Forest-Keeper/issues/18). Описание целевого поведения не заменяет работающую функцию.

| Проверка | Состояние main | Что предъявить для полной приёмки |
| --- | --- | --- |
| Clone → setup → первый вход | Реализовано; инструкция исправлена | Отчёт fresh clone на конкретном SHA |
| Два источника, импорт CSV/XLSX/XML, raw/provenance | Этап 2 принят | Проверка собственного файла и открытого примера |
| Нормализация и история правил | Этап 3 принят; только явные профили | Подходящий mapping, исходные/нормализованные значения |
| Matching/evidence | Этап 4 принят в main; независимый retest и CI merge commit PASS | Промышленный pilot domain и проверка реальных файлов |
| Conflict Engine | BLOCKED в runtime: ТЗ и DoD зафиксированы в [issue #21](https://github.com/SergeyRassohin/Forest-Keeper/issues/21) | Отдельный PR Stage 5, реальный Conflict с deterministic evidence, restart persistence и зелёный merge CI |
| Human Review + Decision Registry | BLOCKED: этапы 6–7 не реализованы | Сохранённый Decision, actor/reason/context и immutable history |
| Restart с сохранением Decision | BLOCKED: нет Decision | Проверка того же ID после restart без удаления volumes |
| Similar Decision/recommendation | BLOCKED: нет retrieval/recommendation | Следующий похожий кейс с реальной ссылкой на прошлый Decision |
| Pinned Qwen artifacts | Manifest и lock проверяются; есть downloader | Полная локальная SHA-256 проверка файлов |
| LLM/embedding runtime + model-info | BLOCKED: нет поддерживаемого запуска | Точные ID/revisions; inference и 1024 dimensions smoke |
| AI evidence / offline / LLM failure | BLOCKED: нет интеграции | Только реальные evidence IDs; офлайн-тест; работа истории без LLM |

**Итог: полная внешняя приёмка MVP пока BLOCKED.** Можно проводить техническую проверку реализованных этапов, честно отмечая границу. Наличие ТЗ Stage 5 не означает наличие работающего Conflict Engine. Эта документация не закрывает #18.

Stage 4: [текущий отчёт и DoD](../testing/reports/stage4-matching-acceptance-2026-10-21.md). Локальные проверки, gold, 100k capacity и restart выполнены; [отдельный independent runtime/security retest](../testing/reports/stage4-matching-independent-2026-10-21.md) PASS без блокирующих замечаний, повторены 619 тестов и все четыре capacity профиля. Владелец принял HEAD `f44e01e` и разрешил merge; main merge `bea0d55c92540744657feac863084cde131a7f43`, [CI — SUCCESS](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39595762080). Шаг 1 / Stage 4 из #20 завершён.

Stage 5: подробное ТЗ, границы, benchmark, migration, browser E2E, recovery и merge gate зафиксированы в [issue #21](https://github.com/SergeyRassohin/Forest-Keeper/issues/21). Реализация должна идти отдельным PR и остановиться на `READY TO MERGE` до отдельного разрешения владельца.

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
