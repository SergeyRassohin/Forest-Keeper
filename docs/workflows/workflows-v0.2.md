# Forest Keeper — Workflows v0.2

## WF-01 Observer
1. FK получает данные из разрешённых источников.
2. Выполняет нормализацию, сопоставление и проверки.
3. Незначимые события фиксируются без ручной задачи.
4. Значимые случаи становятся Issue/Conflict.
5. Формируется рекомендация.
6. Случай маршрутизируется нужной роли.
7. Решение фиксируется в Decision Registry и Audit.

Observer не блокирует исходные системы.

## WF-02 Advisor
1. Пользователь видит конфликт/аномалию.
2. FK показывает источники, значения, provenance и основание.
3. FK показывает похожие подтверждённые случаи.
4. Формируется рекомендация.
5. Пользователь принимает решение.
6. Решение сохраняется.

## WF-03 Post-check
1. Данные уже появились в исходной системе.
2. FK получает выгрузку или событие.
3. Выполняется анализ.
4. При проблеме создаётся Human Review.
5. Исправление выполняется человеком или будущим controlled publisher.

## WF-04 Controlled Gateway — будущее
1. Кандидат на изменение поступает в FK.
2. FK возвращает PASS / WARNING / REVIEW.
3. PASS означает только отсутствие основания блокировать.
4. REVIEW требует Human Decision.
5. Критическая публикация возможна только после APPROVED.

## MVP workflow
`1C XML + Excel → adapters → raw storage → normalization → matching → conflict detection → recommendation → human decision → Decision Registry → next similar recommendation`


## Stage 6: реализованный human workflow

Conflict evidence → явное начало рассмотрения → допустимый outcome + reason → подтверждение → атомарный Decision/lifecycle/audit → receipt → Registry/history. Исправление — новый Decision с supersedes, без переписывания старого. [Пошаговый сценарий](../development/human-review.md). Bounded retrieval принят отдельно как Stage 7; recommendation runtime/AI/write-back отсутствуют.

## Stage 7 bounded retrieval — принят в main через PR #28

New Conflict → scope/permission → versioned structured context → background query preparation if absent → scoped eligibility/compatibility → complete active pgvector representation → exact cosine top-N → real historical Decision IDs → human reads actual history. No proposed action and no automatic Decision. Production provider unavailable is explicit and preserves Registry/review. [Workflow and recovery](../development/similarity-retrieval.md).

## Stage 8 Recommendation Engine — предложение по issue #29

[Архитектура и численная demo policy](../development/stage8-recommendation-proposal.md) подготовлены до реализации. Owner approval policy ожидается; это ещё не работающий recommendation workflow. Фактический Stage 6 объединил Human Review + Registry; нынешние Stage 7/8/9 соответствуют старым roadmap 8/9/10. Следующий Stage 9 — AI/LLM integration, не часть текущего Stage 8.
