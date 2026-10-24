# Stage 8 — independent proposal review

Дата: 24 октября 2026. Ветка: `codex/stage8-recommendations`; исходный принятый Stage 7: `c927af513d29d83bd53b1b6522efccb42b5a1341`.
Предмет: [architecture/policy proposal](../../development/stage8-recommendation-proposal.md) и proposed Decision Log entry по [issue #29](https://github.com/SergeyRassohin/Forest-Keeper/issues/29), §§6.7,11,13. Проверенный SHA-256 текста proposal: `9d4dd635a4366ea762c1f92a5e37f2271cbf0b4bdfdf9274a6c2f5b67b712585` (это идентификатор рассмотренного содержания, не owner approval).

**Итог: proposal пригоден для предметного рассмотрения владельцем; неустранённых блокирующих архитектурных замечаний к предложению нет. Это не owner approval численной политики, не разрешение начать её реализацию и не приёмка Stage 8.**

Владелец должен явно утвердить конкретную версию/commit предложения. До этого положительная recommendation business logic остаётся не реализованной и не включённой. Статус будущих Stage 8 acceptance/runtime/security/performance gates — NOT RUN. Никакой READY TO MERGE бизнес-реализации этим review не объявляется.

## Проверенная граница

Read-only сопоставлены issue #29, proposal/Decision Log, AGENTS, canonical Recommendation/Decision model и lifecycles, текущие Stage 6/7 auth/Decision/retrieval/activation paths, API target и XLSX. Reviewer не изменял source/Git/services/данные и не запускал тесты; записан только этот отчёт. В рабочем дереве Stage 8 business module/runtime policy отсутствуют, изменения ограничены документацией.

- Существующий модульный монолит, scoped Stage 7 retrieval и Human Review остаются основой. Qwen/LLM, новый embedding provider, RuleSuggestion, Rules/Templates/Codex mutation и write-back исключены.
- Production с synthetic/test provider не получает положительное предложение. Отсутствующие authority/rules показываются как NOT_DEFINED/NOT_CONFIGURED; SourceSystem type/name/filename/authority_scope metadata не становятся правилом истины.
- API outcomes RECOMMENDED/ABSTAINED/UNAVAILABLE отделены от canonical Recommendation CURRENT/STALE/SUPERSEDED. Recommendation не получает ACCEPTED и не превращается задним числом в Decision. Stateless result плюс immutable audit receipt — допустимый предложенный bounded вариант из issue §8; его доказательность ещё предстоит проверить.
- Единственный business commit path — существующий подтверждённый человеком Decision POST. Исторические Decisions/evidence не переписываются. Optional server-validated receipt не даёт полномочий и не переносит historical source/value UUID в current Conflict.

## Права и confidence

XLSX прочитан независимо через его XML; checksum каталога совпадает, permissions39:

| Действие | XLSX роли |
|---|---|
| recommendation.view | VIEWER,REVIEWER,DATA_OWNER,ADMIN |
| recommendation.accept_as_decision | REVIEWER,DATA_OWNER |
| decision.create / conflict.review.start | REVIEWER,DATA_OWNER |

Proposal соответствует матрице. ADMIN не получает business authority, scope не выводится из роли. Receipt path должен проверять permissions на сервере, а не только скрывать UI-кнопку.

Предложенный `confidence=G` с единицей INDEPENDENT_PROVENANCE_GROUPS является абсолютной мерой поддержки, не cosine/probability/процентом. В canonical model нет обязательного диапазона0..1; старый API пример0.86 требует явного обновления контракта, а не молчаливой подмены смысла. Null при abstain/unavailable не выдаёт недоступность за нулевую вероятность.

Minimum5, вес1 на группу, agreement100%, zero contradictions/dominance margin1, evidence window20 и byte cap64KiB — **только PROPOSED**. Reviewer не является владельцем и не утверждает эти значения. Отказ при scoped total_above_threshold>20 исключает скрытое игнорирование противоречий за top-N.5:1 и внутригрупповой конфликт дают abstain, не majority vote. Несогласованный ENTER_VALUE не исчезает из denominator. Различие между одно-прецедентным demo из §2 и minimum5 открыто вынесено на owner decision.

## Исправленные проектные риски

1. Корреляция теперь учитывает любой общий input file SHA, shared RawRecord, scoped business key и semantic evidence fingerprint; новые UUID/imports не создают независимость. Полный graph строится вместе с current sentinel до исключений; весь current-connected component контекстный. Цепочка current—A—B не оставляет B ложной независимой поддержкой.
2. Source correspondence — явный versioned server declaration с проверяемыми current/historical IDs/types/profile lineage. Нельзя угадывать A/B или «1С». Scope slice, ambiguity и unknown provenance обработаны fail-closed.
3. После begin_review меняется token: старый reference/draft сбрасывается, recommendation запрашивается заново. Предложение для OPEN не отправляется под новым IN_REVIEW token.
4. Одного current Conflict row lock недостаточно для concurrent historical heads/новых Decisions/revoke/activation. Proposal теперь описывает database/schema-scoped shared/exclusive transaction gate, preflight permissions до exclusive gate и повторную auth/scope проверку после него; участвующие write paths перечислены. Это конкретный проверяемый вариант, а не обещание, что TOCTOU уже устранён.
5. Exact idempotent replay после свежих прав/scope проверок возвращает исходный committed receipt до новой stale/recompute проверки. Новый key со stale reference отклоняется. Это сохраняет Stage 6 lost-response/retry семантику; revoke не обходится старым receipt.
6. Receipt означает показанную рекомендацию. MATCHED/OVERRIDDEN выводится сервером по фактическому human action/current IDs; клиентский accepted flag не используется, manual override не выдаётся за принятие.
7. Audit dedup использует immutable event и исходный generated_at. Manifest сохраняет рассмотренные<=20 IDs/scores/groups/exclusions/hashes и retained references для reconstruction, используемый scoped mapping slice вместо global declaration с чужими IDs. Предложенный byte cap отказывает без усечения оснований; secrets/raw/human reasons/vectors в audit не копируются.

## Цена атомарного receipt и обязательные будущие проверки

Coarse gate координирует Decision/review-start, поддерживаемые auth/scope revocations и active retrieval activation. Это затрагивает несколько модулей и может создавать contention; данный tradeoff явно передаётся владельцу. Manual save сохраняет независимость от Redis/provider/config, но даже его shared gate wait обязан быть bounded. Lock wait/recompute/commit используют один monotonic remaining budget, а не полный1500ms на каждую SQL фазу.

Preflight auth не должна оставлять устаревшую identity map/snapshot для повторной проверки. Прямые SQL изменения оператором вне cooperating paths не защищены advisory lock и требуют согласованного quiesce; mixed-config rolling deployment не поддержан. Новая policy/mapping config активируется только после drain всех API/worker instances и проверки одинаковых digest. Эти ограничения нужно сохранить в реализации и эксплуатационной инструкции.

До code acceptance обязательны реальные barrier tests для новых eligible Decisions/phantoms, supersede/reopen, scope/session/permission loss, active version change, двух reviewers, rollback/restart/lock release, идемпотентности и manual save при Redis/provider failure; отдельно измерить contention/starvation и NFR. Если протокол не проходит, receipt acceptance остаётся fail-closed и архитектура пересматривается до внедрения. No-schema решение не является заранее доказанным отсутствием необходимости миграции.

Все14 Stage 7 carry-over вопросов имеют явный proposed disposition, предложенного owner и acceptance/blocker: production semantics блокируется;100k/fully cold/широкие unit families/Codex/license-update/full external MVP не объявлены выполненными. Stage 8 сохраняет обязательные100/1k/10k и10-session measurements, общий similarity/recommendation rate budget и bounded retrieval. Старые Stage 7 PASS не являются новыми Stage 8 результатами.

## Передача владельцу

Можно подготовить draft PR с этим proposal/Decision Log и исправлением current-status docs. Конкретные будущие module/API/schema/file changes перечислены; `tests/ui-gallery/gallery.spec.ts` — действительный gallery path. Пути документов раскрыты до repository paths; preflight transaction закрывается до новой gated transaction с fresh ORM state; обход advisory gate прямыми operator SQL явно ограничен quiesce. Эти заключительные уточнения проверены в указанном digest proposal.

Следующий gate — **OWNER_APPROVAL_REQUIRED**, привязанный к конкретному commit/digest policy package. После approval потребуются реализация, новые самостоятельные tests/evidence, independent final review и зелёный exact-final-HEAD CI; затем только READY TO MERGE без автоматического merge. #17/#18/#20 и future Stage 9 не закрываются данным предложением.
