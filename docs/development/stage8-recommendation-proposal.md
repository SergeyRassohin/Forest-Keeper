# Stage 8 — предложение архитектуры и политики v1

Дата: 24 октября 2026, Europe/Moscow. Основание: [issue #29](https://github.com/SergeyRassohin/Forest-Keeper/issues/29), §6.7 и §13.
**Статус: PROPOSED / OWNER_APPROVAL_REQUIRED. Это проект решения, не принятая бизнес-политика и не отчёт о реализации.**

Предлагаемый пакет для владельца: только маркированный demo-режим; минимум пять
независимых групп и ни одного противоречия; явное назначение соответствующих источников;
число оснований вместо процента «вероятности»; ручное подтверждение в прежней форме.
Один прошлый случай показывается как контекст, но пока не даёт готового действия.
Далее приведены точные параметры, альтернативы и будущие проверки этого предложения.

## Входной gate и граница

Рабочее дерево перед началом чистое. От `main` создана отдельная ветка `codex/stage8-recommendations`.
Stage 7 принят владельцем через [PR #28](https://github.com/SergeyRassohin/Forest-Keeper/pull/28),
merge `c927af513d29d83bd53b1b6522efccb42b5a1341`;
[CI именно merge SHA — SUCCESS](https://github.com/SergeyRassohin/Forest-Keeper/actions/runs/40079346518).
Рассмотрены AGENTS, канонические документы, XLSX, Stage 6/7 код и ограничения,
issue #27, PR #28 и его acceptance/review, #17/#18/#20.

Нумерация фактических этапов: Stage 6 объединил Human Review и Decision Registry;
Stage 7 = Similar Decision Retrieval (старый roadmap: 8);
Stage 8 = Recommendation Engine (старый: 9);
Stage 9 = AI/LLM integration (старый: 10). Исторические отчёты сохраняют прежнюю нумерацию.
Будущий Forest Codex workstream #17 сохраняет свою историческую ссылку «Stage 11»;
его перенумерация и реализация этим предложением не утверждаются.

Stage 8 добавит deterministic RecommendationService в существующий модульный монолит.
Qwen/LLM, новый embedding provider, RuleSuggestion, изменение Rules/Templates/Codex,
write-back и автоматические Decisions исключены. 39 permissions XLSX не меняются.
Production semantic quality не доказано; production recommendation по test vectors запрещена.

## Архитектура и публичный контракт

Поток: scoped Conflict + frozen context → существующий Stage 7 retrieval →
валидация provenance/source correspondence → чистая deterministic policy →
RecommendationResult → существующий Human Review.
Не делать внутренний HTTP-вызов similarity API и повторную аутентификацию:
переиспользовать service в одной read-only REPEATABLE READ транзакции,
начатой **до** чтения сессии, ролей и scope.

Один новый маршрут: `GET /api/v1/conflicts/{id}/recommendation`.
Cookie-session; существующие `conflict.view`, `decision.view`, **`recommendation.view`**
и `data_domains`; unknown/not-in-scope одинаково 404. Включение в существующую форму
требует также `recommendation.accept_as_decision` и обычных business permissions.
ADMIN и VIEWER могут читать разрешённые результаты, но не принимать бизнес-решение.
Не добавлять POST «accept», bearer или клиентские overrides threshold/policy/source map.

Схема результата:

- `status`: RECOMMENDED / ABSTAINED / UNAVAILABLE — только outcome API, не lifecycle enum.
- `recommended_action`: SELECT_VALUE либо null. ENTER_VALUE пока только контекст истории:
  без применимых проверенных business rules перенос исторического введённого значения запрещён.
- `recommended_source_id`, `recommended_value_id`, typed `recommended_value`:
  только из **текущего** frozen Conflict и существующей `selectable/resolve_value` проверки;
  при любом отказе все эти поля null.
- `confidence`, `confidence_unit`, `confidence_label`: предложенная мера количества
  независимых согласованных групп ниже; не cosine и не вероятность.
- `reason_code`, `reasoning_summary`, `evidence_summary`, `limitations`,
  `conflicting_evidence`, `supporting_decision_ids`, `rules_used`, `authority_reference`.
- `quality_provenance` (DEMONSTRATION_ONLY / NOT_AVAILABLE), `retrieval_version`,
  точный model metadata, `recommendation_policy_version`, `source_mapping_version`,
  `context_fingerprint`, `review_context_version`, `generated_at`, `audit_reference`.

Все evidence IDs/сводки разрешены этому actor в той же snapshot. Правила/шаблон
возвращают NOT_CONFIGURED, authority — NOT_DEFINED; source correspondence не означает
авторитетность. Ни существующий `authority_scope={...}` metadata, ни название файла,
ни тип ONE_C сами по себе не являются действующим правилом выбора истины.

Состояния текущего Conflict: OPEN или IN_REVIEW без прежнего head допускают оценку;
RESOLVED/INSUFFICIENT_DATA и явный пересмотр с прежним Decision head дают
ABSTAINED / CURRENT_CASE_NOT_ELIGIBLE. DEFERRED head также исключает готовое предложение
в этой первой политике. Previous-profile/stale context → ABSTAINED / STALE_CONTEXT.
GET не начинает review и не меняет текущий token/lifecycle.

Коды first-class отказов: POLICY_NOT_APPROVED, SOURCE_MAPPING_NOT_CONFIGURED,
SOURCE_MAPPING_AMBIGUOUS, INSUFFICIENT_INDEPENDENT_EVIDENCE, CONTRADICTORY_PRECEDENTS,
UNSUPPORTED_HISTORICAL_ACTION, EVIDENCE_WINDOW_EXCEEDED, CURRENT_CASE_NOT_ELIGIBLE,
STALE_CONTEXT, AUTHORITY_UNVERIFIABLE. Отсутствующие authority/rules сами по себе
не запрещают явно маркированную demo-рекомендацию по памяти; они всегда видимы как ограничения.
Унаследовать различия Stage 7: NO_HISTORY/NO_ACCESSIBLE_PRECEDENT,
NO_COMPATIBLE_PRECEDENT/BELOW_THRESHOLD, INDEX_NOT_READY/QUERY_CONTEXT_PENDING,
PROVIDER_UNAVAILABLE, *_INTEGRITY_FAILURE. Отдельно RETRIEVAL_TIMEOUT/AUDIT_UNAVAILABLE.
401/403/404/422/429 остаются HTTP access/validation errors, без выдачи cached evidence.
Операционная ошибка БД — sanitized 503; недоступный provider может дать типизированный
UNAVAILABLE с confidence=null. Не заменять недоступность нулевой уверенностью.

## Предлагаемая policy `stage8-demo-unanimous-v1` — требуется одобрение

Это **только demonstration policy**. До явного утверждения владельцем положительная
ветка не реализуется/не включается; missing approval даёт POLICY_NOT_APPROVED.
Одобрение фиксируется в Decision Log со ссылкой/датой и digest неизменного содержания
политики. Будущая смена чисел, grouping или mapping semantics требует новой версии.
Обычная production конфигурация остаётся UNAVAILABLE: в ней нет принятого provider
и нет реализованной активной scoped authority/rule. Одобрение demo policy это не меняет.

| Выбор | Предлагаемое точное значение | Обоснование / граница |
| --- | --- | --- |
| Similarity gate | прежнее >=0.85, full precision | Утверждённый Stage 7 gate; не показатель правильности |
| Evidence window | один вызов retrieval: limit=20, offset=0 | Сохраняет max Stage 7 и ограничивает работу |
| Полнота | при scoped `total_above_threshold > 20` — abstain | Нельзя игнорировать противоречия за top-20 или обходить лимит пагинацией |
| Minimum | **5 независимых групп** | Явный fixture roadmap; одна группа не доказывает практику |
| Веса | **1 на группу**, similarity только фильтр | Не усиливать synthetic score и количество клонированных строк |
| Agreement | **100%** всех пригодных групп | Никакого молчаливого голосования |
| Disagreement bound | **0** противоречащих групп/исходов | Даже 5:1 → abstain; конфликт внутри группы тоже veto |
| Dominance margin | `(winner_groups - runner_up_groups) / all_groups = 1` | Иная margin означает противоречие, не готовый выбор |
| Confidence formula | `G = число независимых групп`, `confidence=G` только при RECOMMENDED | Абсолютная evidence measure, **не** диапазон 0..1 |
| Confidence unit | `INDEPENDENT_PROVENANCE_GROUPS` | API/UI прямо называют единицу; не показывают % |
| Confidence bands | 0 → NO_EVIDENCE; 1..4 → INSUFFICIENT_EVIDENCE; 5..20 unanimous → SUFFICIENT_DEMONSTRATION_EVIDENCE | При ABSTAINED/UNAVAILABLE numeric confidence=null; разрешённое число групп отдельно в evidence summary |
| Ties / mixed ENTER_VALUE | abstain | Никакой выбор по UUID, свежести, «победившему» большинству или перенос correction |

### Соответствие источников

В production нет активной mapping-конфигурации. Для изолированного demo — явный,
versioned, server-controlled declaration: domain/entity/attribute + logical source roles →
конкретные допустимые SourceSystem IDs **и** ожидаемые frozen source types/profile hashes.
Например, роли ACCOUNTING_EXPORT и REGISTER_EXPORT с точно назначенными идентификаторами;
это имена соответствия источников, не новые canonical roles User и не authority rules.
Файл конфигурации конкретного стенда вне Git/клиентских POST, его schema/policy — в Git;
hash версии и полный **использованный scope slice** declaration сохраняются в audit,
без записей иных областей. Включение — trusted operator
после явного назначения соответствия; не выводить его из source name/code, порядка A/B,
расширения CSV/XML или одного source_type. Без назначения: abstain.

Каждая историческая выбранная source/value reference обязана присутствовать в её frozen
evidence и однозначно принадлежать логической роли; обе стороны current/historical case
покрыты declaration и согласованы с frozen type/lineage. Сопоставление current logical role
должно дать ровно одну допустимую текущую EntityValue reference. Исторический UUID/value
никогда не копируется в новый Conflict. Unknown/legacy metadata, повтор роли, несовместимый
scope/profile и неизвестный SourceSystem → abstain. Обновление declaration создаёт новую
версию и инвалидирует производные рекомендации; исторические Decisions не переписываются.

### Независимость / корреляция

Группировать **до** подсчёта поддержки, не по actor или новым UUID. Ребро корреляции между
историческими случаями появляется при любом совпадении: **хотя бы один** общий исходный
file SHA-256 (независимо от SourceSystem/ImportBatch/RawRecord UUID и порядка сторон),
общий RawRecord, одинаковый непустой scoped business key,
либо одинаковый semantic frozen evidence fingerprint без UUID/time/actor/outcome.
Группа — connected component этих связей; каждая даёт вес 1. Для production нельзя
считать отсутствие признака корреляции доказательством независимости: эта модель
пригодна только для маркированной демонстрации, не industrial quality acceptance.
Сначала строится полный граф всех <=20 пригодных прецедентов **вместе с current case**.
Весь connected component, содержащий current case, не поддерживает предложение,
а показывается только как коррелированный контекст. Не удалять прямого соседа до
построения компонент: цепочка current—A—B делает B также зависимым.
Отсутствующий/сомнительный provenance → abstain, а не «каждый UUID независим».
Несогласие selected role внутри одной группы также veto. Несколько исходов ENTER_VALUE
или смесь SELECT_VALUE/ENTER_VALUE остаются контекстом с явным отказом; они не пропадают
из denominator для получения удобного consensus.

Заведомо консервативная группировка может отклонить реальные независимые случаи;
расширение требует отдельного owner decision и нового fixture. Пять независимых demo cases
должны реально пройти отдельные импорты/разные бизнес-ключи/разный evidence, сохраняя
совместимость и >=0.85; нельзя размножить одну запись или назначить `independent=true`.

### Golden fixtures до включения

Это приёмочные ожидания предложения, **ещё не выполненные тесты**:

| Сценарий | Ожидаемый результат |
| --- | --- |
| 0 доступных прецедентов | ABSTAINED, без сведений о чужой истории |
| 1 подходящий реальный Decision A → новый B | Ссылка на A как контекст; недостаточно для готового действия |
| 4 независимых согласованных | ABSTAINED / INSUFFICIENT_INDEPENDENT_EVIDENCE |
| 5 независимых SELECT_VALUE одной logical role | RECOMMENDED только в одобренном demo, actual current IDs, confidence=5 groups |
| 5 клонированных Decisions / хотя бы один общий файл | Одна группа, abstain |
| 5 разных импортов, но тот же business key/evidence | Одна группа, abstain |
| Current—A по файлу, A—B по business key | Вся current-component контекстная; B не считается независимым |
| 5 поддерживают, 1 выбирает другую роль | ABSTAINED / CONTRADICTORY_PRECEDENTS с разрешёнными примерами |
| Противоречие внутри одной коррелированной группы | ABSTAINED; majority не используется |
| A/B переставлены, явное correspondence сохранено | Та же logical role → текущий value ID, не historical ID |
| Unknown role/type либо два current sources для роли | ABSTAINED, не угадывать по «1С» |
| ENTER_VALUE; неверный type/unit или mixed actions | ABSTAINED, historical values только контекст |
| Similarity ровно 0.85 / чуть ниже | Inclusive Stage 7 boundary / BELOW_THRESHOLD; округление не влияет |
| 20 пригодных unanimous / 21 пригодный | Допускается / EVIDENCE_WINDOW_EXCEEDED, даже если первые 20 согласны |
| Отзыв scope, supersede/reopen, смена version/mapping | Следующий запрос пересчитывается; UI сбрасывает старый draft |
| Partial/corrupt index, NaN/Inf, fingerprint mismatch | INDEXING/UNAVAILABLE без частичного предложения/внутренних ошибок |
| Активная authority противоречит практике (adapter fixture) | ABSTAINED; не подменять ни authority, ни память |
| Production с test flags, даже 20 согласованных | UNAVAILABLE, без положительного synthetic recommendation |
| Policy approval отсутствует/неверный digest | POLICY_NOT_APPROVED, положительная ветка закрыта |

Одношаговый demo из §2 issue #29 читается как объяснимый контекст прошлого решения,
а готовое действие появляется только после пяти независимых групп (§6.7).
Это спорный выбор для утверждения владельцем, а не молчаливое ослабление minimum=5.

## Provenance, audit и подтверждение человеком — предлагаемое решение

Начать **без новой таблицы Recommendation и без Alembic migration**. Два разных статуса:
API outcome и canonical Recommendation CURRENT/STALE/SUPERSEDED не смешивать.
GET рассчитывает snapshot результата; browser считает его актуальным только для данного
review token + policy/mapping/retrieval/evidence fingerprint. Изменение dependency требует
нового GET; прежний snapshot сохраняет прежний смысл, не переписывается как новый результат.

Для воспроизводимости предложен bounded append-only `RECOMMENDATION_EVALUATED` AuditEvent
в уже существующей таблице, после закрытия read-only transaction, отдельной короткой записью.
Deterministic event ID: actor + conflict + fingerprint + policy/mapping/retrieval + outcome;
повтор того же результата — INSERT ON CONFLICT DO NOTHING, не UPDATE.
`generated_at` не входит в ID; при повторе возвращается исходный timestamp/audit receipt,
а не новый timestamp поверх старого события. `request_id` связывает безопасный технический
trace с audit, без копирования payload запроса.
Сохранять только actor/case/evidence IDs/versions, policy snapshot/hash и **использованный
scope slice** source mapping (не global declaration с чужими source IDs), review token,
до 20 рассмотренных historical IDs/точных score/групп/exclusion codes и их context hashes,
action current references, outcome/reasons и timestamp. Вместе с immutable Decision context
и retained version artifacts это manifest для reconstruction, не один hash без оснований.
Максимальный сериализованный audit payload — предлагаемые **64 KiB**; превышение даёт
UNAVAILABLE/AUDIT_PAYLOAD_LIMIT, без молчаливого усечения оснований. Никаких human reasons,
raw payload/secrets/vectors в audit. Приёмка должна доказать byte cap и отсутствие
unbounded read/write amplification; исторические данные читаются по тем же scope permissions.
Ошибка audit → UNAVAILABLE/AUDIT_UNAVAILABLE, ручной Human Review остаётся работоспособным.
Обычные read-only запросы не создают бизнес-фактов и не ставят embedding/index jobs:
service retrieval получит optional `prepare_query=False` для этого маршрута;
pending cache → INDEXING. Подготовка остаётся существующему similarity UI/worker/CLI.

В UI «Использовать предложение в форме» только заполняет ручной выбор и раскрывает
текущие значения; причина и финальное подтверждение по-прежнему вводятся человеком.
После успешного `begin_review` (он меняет review token) UI обязательно сбрасывает прежний
recommendation reference/draft и заново запрашивает контекст и recommendation. Предложение
из OPEN нельзя отправить как принятую рекомендацию под новым IN_REVIEW token.
На сохранении — существующий POST Decision со всеми token/head/permission/idempotency
проверками и optional `recommendation_reference` (UUID audit receipt).
Сервер проверяет actor/case/scope, неизменность context/policy/mapping/retrieval/effective
evidence, запрет протухшего результата; клиентские evidence/confidence игнорируются/отклоняются.
Stale supplied reference →409, человек перечитывает контекст либо выбирает ручное решение
без ссылки. Обычное сохранение без reference не зависит от recommendation/Redis/provider.
Reference включается в request hash; idempotent receipt после revoke по-прежнему запрещён.
Это ссылка на **показанную** рекомендацию: сервер выводит MATCHED/OVERRIDDEN из фактического
outcome/current source/value IDs человека; никакого клиентского `accepted=true`.
Ручная смена выбора в UI очищает reference; сервер всё равно валидирует несовпадение,
если reference явно прислан с другим допустимым действием, и не объявляет его принятием.
Только новый Decision получает серверный recommendation snapshot в JSON context и ссылку
в своём audit; старые JSON/Decisions не меняются. Принятие не создаёт Recommendation ACCEPTED.

### Предлагаемый протокол атомарности receipt

Одного row lock текущего Conflict недостаточно: historical heads, scope и активная модель
могут измениться между проверкой receipt и commit. Предлагается transaction advisory gate,
изолированный по database/schema. Порядок: предварительная auth/permission проверка →
gate → повторная auth/scope проверка → case locks; не брать global gate для анонимного
или заведомо не имеющего business permissions запроса.

1. Обычные Decision/review-start writers, поддерживаемые session/scope revocations и
   `activate_version` берут shared gate до своих row locks/изменений. Они остаются
   параллельными между собой; обычный manual Decision не читает recommendation/provider.
2. POST с optional receipt проходит предварительные `decision.create` и
   `recommendation.accept_as_decision` (плюс соответствующие outcome/supersede permissions),
   берёт exclusive gate до case lock, перечитывает из БД session/роли/scope/permissions.
   Preflight transaction заранее закрыта; после gate используется новая DB transaction
   и fresh ORM state, не identity map/старый actor или snapshot предварительной проверки.
   Затем проверяет persistent actor/case/idempotency key: точный прежний payload/hash
   возвращает **исходный committed receipt до stale/recompute checks**, как в Stage 6.
   Другая нагрузка того же key →409. Только новая отправка заново вычисляет bounded current
   evidence/result fingerprint и сравнивает receipt, policy/mapping/retrieval versions и
   review token. Новый key со stale reference →409.
   Gate удерживается до атомарного commit Decision + snapshot + audit; rollback всё освобождает.
3. В этот короткий участок не входят network/RQ/model calls или ожидание человека.
   Lock wait + recomputation + commit ограничены единым monotonic protective budget 1500ms;
   `statement_timeout`/`lock_timeout` перед фазой получают только **оставшееся** время,
   не новый полный budget на каждый SQL. Shared lock wait обычного manual path также
   bounded, нельзя превратить его в неограниченное ожидание exclusive receipt transaction.
   исчерпание → sanitized503, без partial write, возможен прежний idempotent retry.
   Проверить NFR и starvation: optional receipt не должен длительно блокировать manual save.
4. Policy/source mapping неизменны внутри процесса и не hot-reload. Operator activation
   новой release config требует остановить приём запросов/дождаться in-flight транзакций
   **во всех API/worker instances**, заменить config, проверить одинаковые digest и
   возобновить работу. Mixed-config rolling deployment не считается поддержанным этим
   bounded протоколом. Автоматический distributed config control plane не добавляется.
   Прямые operator SQL изменения users/roles/sessions/retrieval state, обходящие application
   gate, также поддерживаются только при quiesce. Advisory lock не ограничивает DB superuser;
   это проверяемый протокол поддерживаемых application write paths, не DB-wide enforcement.
5. GET по-прежнему использует snapshot и не держит gate до будущего подтверждения человека.
   Конкурентный commit после его snapshot виден следующему GET/receipt validation;
   historical receipt сохраняет смысл «показано тогда», не обещание вечной актуальности.

Цена этого варианта — явная координация нескольких существующих write paths.
Её приемлемость и отсутствие lock-order regression должны проверить targeted independent
barrier tests: new Decision/supersede/reopen, revoke, activation до/во время receipt save;
два reviewers; restart/lock release; repeated idempotent payload; manual save без Redis.
Если протокол не проходит эти проверки/NFR, receipt acceptance остаётся fail-closed;
новая persistent Recommendation entity или смена протокола сначала требует отдельной
поправки к предложению и оценки миграции. Здесь нет заявления, что гонки уже исправлены.

## Лимиты и отложенные вопросы Stage 7 (§9 issue #29)

Каждый owner ниже — **предложенное распределение ответственности**, не назначение
конкретного человека без его согласия. «Владелец» = product owner репозитория,
«разработчик Stage 8» = исполнитель текущего PR. Основание всех disposition: #29 §9,
а для будущего Codex — также #17. Статус реализации этих gate пока NOT RUN.

| № | Disposition | Предлагаемый owner / acceptance или blocker |
| --- | --- | --- |
| 1 | BLOCK_PRODUCTION_RECOMMENDATION | Владелец Stage 9: pinned real provider + representative semantic evaluation; Stage 8 regression production/test flags fail closed |
| 2 | DEFER_WITH_OWNER_AND_ACCEPTANCE | Владелец capacity follow-up: 100k **actual Decisions/vectors**, realistic distribution, 10 sessions/NFR; до отчёта никаких 100k claims |
| 3 | RESOLVE_STAGE8 | Разработчик Stage 8: golden five-independent/five-correlated/mixed cases, grouping hashes; synthetic fixtures не industrial evidence |
| 4 | DEFER_WITH_OWNER_AND_ACCEPTANCE | Владелец performance follow-up: отдельный controlled host с cold OS cache; Stage 8 warm/PG-restart profiles отдельно, старый результат не fully cold |
| 5 | DEFER_WITH_OWNER_AND_ACCEPTANCE | Владелец domain policy: утверждённая dimension/family map + fixtures; Stage 8 exact existing compatibility / unknown fail closed |
| 6 | RESOLVE_STAGE8 | Разработчик Stage 8 + владелец mapping: explicit declaration и legacy/ambiguous negatives; до назначения — abstain |
| 7 | DEFER_WITH_OWNER_AND_ACCEPTANCE | Владелец #17: active scoped/versioned Rules/Templates/Codex и impact/stale; Stage 8 NOT_CONFIGURED/NOT_DEFINED без shadow-rules |
| 8 | RESOLVE_STAGE8 | Владелец утверждает policy; разработчик + независимый reviewer проверяют golden/adversarial cases и label, без %/probability |
| 9 | RESOLVE_STAGE8 | Разработчик + независимый reviewer: barrier tests revoke/supersede/reopen/activate/save, coherent GET и rejection stale receipt |
| 10 | RESOLVE_STAGE8 | Разработчик: corrupt below-threshold/lineage/coverage/fingerprint/NaN/Inf → ни partial recommendation, ни leak |
| 11 | RESOLVE_STAGE8 | Разработчик: общий similarity+recommendation bucket <=120 reads/min, один bounded retrieval; общий request DB deadline 1500ms, timeout sanitized; p95<=1s/10 sessions сохраняется |
| 12 | RESOLVE_STAGE8 | Разработчик: текущие status docs/README обновлены, historical reports не переписаны |
| 13 | DEFER_WITH_OWNER_AND_ACCEPTANCE | Владелец #18/#20: внешний reviewer/fresh clone + Stage 9 Qwen gates; Stage 8 готовит свой non-AI vertical/restart, issues остаются OPEN |
| 14 | DEFER_WITH_OWNER_AND_ACCEPTANCE | Владелец release/security: отдельные license/update/offline supply gates; no scope expansion, existing hardening regressions |

1500ms — общий protective SQL deadline запроса, не новый timeout для каждой фазы.
120/minute — **общий** actor bucket двух read endpoints, а не дополнительная квота,
никаких циклов по страницам/неограниченных history loads. Не менять migration/API defaults.
Benchmark Stage 8: 100/1k/10k actual Decisions/vectors, p50/p95/max, 10 sessions,
abstain/failure distribution, RSS и планы SQL; отдельно показать latency самого retrieval
и добавку policy/audit. 100k и fully cold OS cache остаются unverified.

## Точный план файлов / API / schema

Пути ниже — **план**, отсутствие файла до implementation ожидаемо.

| Новые файлы | Назначение |
| --- | --- |
| `backend/app/recommendations/__init__.py` | Граница модуля |
| `backend/app/recommendations/schemas.py` | Строгий typed API result/reason/quality contract |
| `backend/app/recommendations/policy.py` | Утверждённая pure aggregation/abstention, immutable policy hash |
| `backend/app/recommendations/policies/demo-unanimous-v1.json` | Versioned policy после approval; до него этого runtime файла нет |
| `backend/app/recommendations/evidence.py` | Frozen lineage, grouping, explicit source correspondence |
| `backend/app/recommendations/service.py` | Snapshot orchestration, fingerprint/provenance; no business writes |
| `backend/app/recommendations/routes.py` | Единственный GET, existing auth/rate/deadline contract |
| `backend/app/recommendations/audit.py` | Bounded deduplicated receipt, validation/stale checks |
| `backend/app/common/basis_lock.py` | Только schema-scoped transaction gate primitive и единый lock order |
| `backend/tests/test_recommendations.py` | Golden policy, schema, corruption/hostile inputs |
| `backend/tests/test_recommendations_integration.py` | Actual DB/RQ/API/scoped evidence, GET immutability/races |
| `backend/tests/recommendation_fixtures.py` | Real independent/correlated import→human fixtures |
| `backend/tests/benchmark_recommendations.py` | 100/1k/10k persisted history, 10 sessions |
| `backend/tests/restart_recommendations.py` | Own-project HTTPS restart/error/recovery, retain business volumes |
| `frontend/src/Recommendation.tsx` и `Recommendation.test.tsx` | First-class abstention / honest demo UI / manual form bridge |
| `frontend/src/recommendationTypes.ts` | API types, без новых бизнес-enums |
| `tests/e2e/recommendations.spec.ts` | Own files, five independent, contradictions, override, revoke/roles |
| `docs/development/recommendations.md` | Реализованный контракт/операторский запуск после реализации |
| `docs/testing/stage8-recommendation-acceptance.md` | Исполнимый acceptance checklist, без ложных PASS |
| `docs/testing/reports/stage8-*` | Actual reports с source SHA, после выполнения |

| Изменяемые существующие файлы | Изменение |
| --- | --- |
| `backend/app/main.py` | Подключение GET router |
| `backend/app/common/config.py` | Server policy/source-map selection, defaults disabled; no client override |
| `backend/app/similarity/routes.py` | Переиспользуемый общий actor rate budget/snapshot guard |
| `backend/app/similarity/service.py` | `prepare_query=False` option, прежний public retrieval сохраняется |
| `backend/app/decisions/schemas.py` | Optional UUID receipt; остальные unknown input fields forbidden |
| `backend/app/decisions/routes.py` | Gate до case lock, fresh auth для receipt path |
| `backend/app/decisions/service.py` | Только optional receipt validation/server snapshot/audit, старый manual save независим |
| `backend/app/auth/routes.py` | Shared gate перед поддерживаемым logout/scope revoke; прежние permissions неизменны |
| `backend/app/similarity/jobs.py` | Shared gate перед active-version change, включая worker/CLI activation |
| `backend/tests/test_decision_validation.py`, `backend/tests/test_decisions_integration.py` | Receipt/retry/stale/revocation и прежний manual path |
| `backend/tests/test_similarity_integration.py` | Совместный rate budget, неизменная Stage 7 семантика |
| `frontend/src/HumanReview.tsx`, `frontend/src/HumanReview.test.tsx`, `frontend/src/decisionTypes.ts`, `frontend/src/Decisions.tsx` | Manual selection/confirmation, receipt, historical provenance |
| `frontend/src/Conflicts.tsx`, `frontend/src/Conflicts.test.tsx` | Recommendation block, abort/refresh/reset/navigation |
| `frontend/src/style.css` | Existing brand/responsive styling при необходимости |
| `tests/ui-gallery/gallery.spec.ts`, `scripts/render-ui-gallery.py`, `scripts/check-ui-gallery.py`, `backend/tests/ui_gallery_accounts.py` | Реальные recommendation/abstain/revocation screens, тот же provenance guard |
| `frontend/public/interface/*` | Только реальные regenerated screenshots/manifest/page после проверки |
| `scripts/check-production.py` | Production recommendation unavailable + review/Registry usable |
| `README.md`, `docs/development/mvp-progress.md`, `docs/development/mvp-development-plan-v0.1.md`, `docs/development/human-review.md`, `docs/development/decision-registry.md`, `docs/development/similarity-retrieval.md` | Текущий статус/нумерация и точная граница каждой подсистемы |
| `docs/api/api-contract-v0.1.md`, `docs/data-model/data-model-v0.2.md`, `docs/development/object-lifecycles-v0.1.md`, `docs/decisions/decision-log.md` | Явное уточнение stateless result vs lifecycle, optional receipt, утверждение policy |
| `docs/architecture/architecture-v0.2.md`, `docs/architecture/technical-stack-and-module-map-v0.1.md`, `docs/architecture/workflow-overview.md`, `docs/workflows/workflows-v0.2.md` | Актуальные boundaries/flows |
| `docs/deployment/review-readiness.md`, `docs/deployment/external-review-quickstart.md`, `docs/security/security-v0.1.md`, `docs/testing/testing-strategy-v0.1.md` | Honest setup/availability/security/acceptance limits |

Не планируются SQL schema/Alembic/ORM changes, XLSX/permission catalog changes,
dependency/model-manifest changes, LLM adapters/runtime/downloads. JSON context новых
Decisions получает additive server-only recommendation provenance, старые JSON читаются
без reinterpretation. Обоснованное отклонение от этого списка сначала отражается здесь.

## Дальнейшая приёмка

После owner approval: implementation → golden/unit/integration/real browser
(own files, real IDs, five independent + correlated + contradiction + unauthorized),
keyboard/Axe/responsive → restart/DB/provider/rate/error gates → 100/1k/10k benchmark →
production unavailable smoke → независимый read-only architecture/security/product review
с собственными targeted tests → исправления → весь обязательный CI на exact final HEAD.

Команды: `check.sh`, `check-sast.sh`, `check-secrets.sh`, `test-security-gates.sh`,
`check-dependencies.sh`, `check-integration.sh` из `scripts/`, плюс real gallery,
production smoke и stage-specific runtime/performance. Нельзя подменять новый acceptance
старыми 256/509/49/13 результатами Stage 7. Существующие пороги не ослаблять.
Остановка реализации — READY TO MERGE после всех gate; merge только отдельным
разрешением владельца. #17/#18/#20 не закрывать, Stage 9 не объявлять выполненным.

**Текущее состояние этого PR: proposal only, pending owner approval.**
Численные правила, source correspondence и receipt design выше предлагаются единым
versioned пакетом; утверждение должно ссылаться на конкретный commit этого документа.
