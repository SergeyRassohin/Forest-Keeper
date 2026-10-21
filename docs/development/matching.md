# Stage 4 — Matching / Entity Resolution

ТЗ: [issue #14](https://github.com/SergeyRassohin/Forest-Keeper/issues/14). Matching определяет возможную идентичность двух записей, не выбирает истинные значения атрибутов и не изменяет исходные/нормализованные данные. Conflict Engine относится к этапу 5.

## Работа в браузере

Импортируйте и нормализуйте каждый из двух источников. В разделе «Сопоставление» выберите два COMPLETED normalization runs одного domain/entity_type и профиль; запустите обработку. Для каждого входа требуется ровно один SourceSystem, импортные пакеты входов не пересекаются. По умолчанию источники различны. История и входные списки имеют постраничный просмотр.

Фильтры показывают MATCHED («Совпадение»), POSSIBLE_MATCH («Требует проверки»), NOT_MATCHED («Разные сущности»). Карточка показывает оба источника, original checksum/position, raw/normalized значения, сигналы, итоговую оценку, вес/вклад, допуск, blocking и версии критериев.

Запуск — существующее `analysis.run` (REVIEWER/DATA_OWNER/ADMIN). Просмотр — `match.view` (все четыре роли). Ручное подтверждение/отклонение POSSIBLE_MATCH — `match.review` (REVIEWER/DATA_OWNER, ADMIN без бизнес-роли запрещён). Обязательны причина и разрешённый Origin/cookie. Терминальные состояния не переоткрываются. Actor/time/reason/from/to фиксируются в Audit и видны отдельно от исходного алгоритмического evidence. Повторная конкурентная попытка получает 409.

## Декларативные профили

JSON: `backend/app/matching/profiles/`; выражения и код не исполняются. У профиля UUID, code/version, engine_version=`fk-matching/1`, domain/entity_type, synthetic flag, identity_rules (списки canonical attributes), strong_negative_keys, blocking identifier/name attributes, ограничения и signals. Signal задаёт attribute_code, algorithm, weight, tolerance и canonical unit. Все атрибуты identity/blocking должны входить в сигналы. В профиле явно зафиксированы threshold policy и отсутствие утверждённых fuzzy thresholds.

Material reference profile синтетический: exact composite **code + name**, негативный ключ code, signals code exact(.5), name token_sort_ratio(.35), mass decimal tolerance0.001kg(.1), manufactured_on exact(.05). Capacity profile использует синтетический стабильный `id` и attribute_01. Реальный pilot domain/namespace ключей по-прежнему требует отдельного согласования.

Identity требует непустых VALID значений и единственной записи с данным составным ключом на каждой стороне. Missing/null/empty/INVALID/UNKNOWN/WARNING не образуют exact identity. Различие сильного ключа даёт NOT_MATCHED; одновременно совпавшее identity rule и отрицательный signal остаются POSSIBLE_MATCH. Неуникальные идентификаторы требуют проверки. Высокая похожесть имени не отменяет разницу уникального кода.

Fuzzy — Unicode NFC, casefold, split/sort токенов, затем симметричная фиксированным порядком строк SequenceMatcher alignment с autojunk=False. Score — 2×число совпавших символов / сумму длин, точное Decimal вычисление и шесть знаков. Максимум строки256 по default, конфигурационный предел512. Long/invalid inputs исключаются из сигнала с диагностикой; не угадываются.

Итог confidence: сумма(score×weight)/сумму всех объявленных weights, missing signal вносит ноль и не уменьшает denominator. Числа и допуски Decimal, единицы должны совпасть с declared canonical unit. Confidence округляется до шести знаков HALF_EVEN; входные значения, quality/value IDs, algorithm, score, weight, weighted contribution, unit/tolerance и причина сохраняются. Оценка не является AI confidence и сама не определяет статус.

**Runtime fuzzy/weighted auto-match отключён:** threshold decision OPEN, auto_match_threshold/review_threshold=NULL. Offline gold benchmark сравнивает .7/.8/.9/.95 без активации их в runtime. Только явные unique identity rules дают автоматический MATCHED; это не production threshold decision.

## Candidate generation и пределы

Без full Cartesian product. Строятся индексы явных composite identity, exact identifier, identifier prefix, нормализованного name prefix и первых двух distinct word prefixes. Порядок — identity→identifier→fallback, затем UUID. По default max_block_size32, max_candidates_per_record16; обе стороны ограничены степенью. Bucket сохраняет не более cap+1 идентификаторов и полный count; oversized группы целиком исключаются из этого blocking key. Другой независимый key всё ещё может дать пару.

Структуры O(N) по числу входных записей/ограниченному числу keys, сравнения ограничены N_left×candidate cap, без N_left×N_right перебора. Повторная загрузка/индексация входов после resume линейна; checkpoint каждые100 left records. Диагностика включает eligible record counts, full Cartesian denominator, oversized groups/hits, omitted caps, records_without_candidates, reduction ratio и coverage_limited. Пропуск пары никогда не означает NOT_MATCHED; COMPLETED означает завершение объявленного ограниченного поиска. UI явно предупреждает об ограниченном охвате.

## История, повторы и критерии

Технический MatchingRun переиспользует canonical AnalysisRun lifecycle: NEW→QUEUED→PROCESSING→COMPLETED/FAILED, QUEUED→FAILED. Завершённые normalization runs не меняются. Каждый запуск сохраняет упорядоченные два input AnalysisRun IDs, normalization profile/hash/engine/source lineage, matching snapshot/hash/engine/threshold policy и actor. Никакого нового business lifecycle не введено.

MatchCandidate содержит ровно canonical fields. UUID5 зависит от run ID и unordered raw pair; DB запрещает self pair и хранит raw_a<raw_b. Technical MatchingPair обеспечивает pair uniqueness внутри run. Повторные активные POST coalesce, duplicate jobs защищены advisory lock. Кандидаты, links, статусы и прогресс фиксируются атомарно. Сначала POSSIBLE_MATCH, затем допустимый auto transition; human confirmed_by заполняется только при явном ручном review.

Новый явный запуск после terminal создаёт новую историю, а не меняет результаты прежней версии. Evidence/origin/links неизменяемы; разрешён только terminal переход POSSIBLE_MATCH с сохранением исходного computed_status. Новое выполнение не наследует автоматически прежний human review — Decision Registry относится к будущему этапу. Нет физического merge/split CanonicalEntity.

Потерянные jobs проверяются при старте worker, периодически штатным RQ maintenance и при новом POST. Свежие данные защищены60s; idle dequeue до105s, maintenance interval30s; занятый единственный worker обслуживает recovery после текущего job. Потерянный NEW публикуется; QUEUED/PROCESSING без действующего job становится FAILED/MATCHING_INTERRUPTED. Новый retry — новый run. PROCESSING после hard-stop может продолжиться с последнего checkpoint без дублей.

Gold Reference/CustomerTemplate пока не настроены: input context явно содержит gold_reference_version=NULL. Synthetic gold dataset — тестовые labels, а не эталон клиента. Полный approved activation/rollback/history/impact UI относится к roadmap11–12. Исторические dependency IDs/hashes позволяют будущий impact lookup. При отличии текущего matching или normalization profile от frozen input read API/UI помечают previous-profile result; пользователь запускает явную новую оценку. Новая конфигурация не переинтерпретирует историю и не добавляет persisted STALE в MatchCandidate enum.

Gold Reference в исторических документах и `gold_reference_version` в техническом контексте — прежнее название Forest Codex. Ручной review кандидата сохраняет статус идентичности, пользователя и причину; он не выбирает истинное значение атрибута и не создаёт Decision Registry.

## Проверка и миграция

Миграция0005 добавляет технические runs/pairs и canonical MatchCandidate, индексы и guards, не делает merge/backfill Stage2/3. Upgrade/repeat и fixture-only downgrade/upgrade проверяются с сохранением raw/EntityValue. Downgrade удаляет matching history и не является безопасным production rollback без backup.

`tests/data/matching/` содержит CSV + synthetic1CXML, исходные cases и независимо зафиксированные MATCH/NOT_MATCH/REVIEW labels; неописанные cross-case pairs NOT_MATCH по synthetic case namespace. Coverage включает точные пары, whitespace/Unicode/unit/date equivalence, опечатки, code collision, variant/near-name traps, missing identifiers, unknown/invalid values и ambiguous duplicate keys.

Из backend: `uv run python -m tests.benchmark_matching_quality` — precision/recall/F1, false merge, unsafe auto on REVIEW, false nonmatch, review rate, candidate reduction и offline threshold sweep. Без порога pilot SLA.

Capacity на disposable PG/Redis: `FK_TEST_INTEGRATION=1 uv run python -m tests.benchmark_matching --records 100 1000 10000 100000`. Existing generator создаёт два набора×30attrs; реальный Import→Normalization→Matching, проверяются физические кандидаты/правильные IDs, caps и отсутствие false merge; 10 sessions измеряют detail и candidate list. SimpleWorker/host memory и время этапов публикуются отдельно от production SLA. Собственные schema/queues/files очищаются.

Текущий [отчёт Stage 4](../testing/reports/stage4-matching-acceptance-2026-10-21.md) содержит результаты gold/capacity/restart, DoD и [завершённый independent runtime/security review](../testing/reports/stage4-matching-independent-2026-10-21.md). Пример для человека, впервые открывшего продукт: [учебные данные и ожидания](../../tests/data/matching/README.md), [пошаговый запуск](../deployment/external-review-quickstart.md#9-сопоставление-и-ручная-проверка-идентичности). Этап принят после отдельного разрешения владельца и merge PR #15: `bea0d55c92540744657feac863084cde131a7f43`, [CI merge commit — SUCCESS](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/39595762080). Это не приёмка полного MVP и не утверждение промышленной точности synthetic profiles.
