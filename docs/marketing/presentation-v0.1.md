# Forest Keeper — презентация v0.1

Статус: актуально на 23 октября 2026. Stage 5 принят по [issue #21](https://github.com/SergeyRassohin/Forest-Keeper/issues/21); отдельный Stage 5.1 готовит фирменный Web UI и реальные экраны, его приёмка фиксируется в PR по [issue #23](https://github.com/SergeyRassohin/Forest-Keeper/issues/23).

Эта презентация является текстовым источником для внешних слайдов. При изменении продукта сначала обновляются инженерные документы и решения, затем этот файл и визуальная версия презентации.

## Визуальный бренд презентации

Презентация **обязана наследовать фирменное направление сайта Forest Keeper**, а не использовать нейтральный шаблон корпоративных «карточек».

Визуальные правила:

- основная идентичность — **лес / хвойный силуэт / природная глубина**, как у публичного сайта;
- базовый фон — глубокий тёмно-зелёный, с лесным слоем и лёгким туманом;
- палитра: pine / moss / sage / cream; янтарный используется только для текущего/следующего этапа и предупреждений;
- типографика едина на всех слайдах, крупные заголовки и много воздуха;
- схемы должны быть встроены в композицию, а не выглядеть набором случайных разноцветных кубиков;
- для версии Forest Codex используется мотив годовых колец дерева;
- на каждом слайде сохраняется узнаваемая лесная полоса/силуэт и wordmark Forest Keeper;
- никакой визуальной стилистики, конфликтующей с сайтом, без отдельного решения по бренду.

Это часть бренда продукта, а не декоративная рекомендация.

## Слайд 1. Forest Keeper

**Корпоративный AI/data intelligence layer над существующими системами.**

Forest Keeper наблюдает данные предприятия, сопоставляет сущности, объясняет расхождения, сохраняет подтверждённые решения людей и использует их в похожих случаях.

Текущий статус:

- этапы 0–5 приняты в `main`;
- Stage 5 Conflict Engine принят через PR #22; следующий этап — Human Review / Decision Registry;
- внешний review планируется на 24 октября 2026.

---

## Слайд 2. Что решает Forest Keeper

Проблема:

- одна и та же сущность существует в 1С, Excel, CRM, PLM и файлах;
- идентификаторы, названия, единицы, форматы и значения расходятся;
- человек вынужден вручную искать, что относится к одному объекту и чему доверять.

Forest Keeper:

- сохраняет raw и provenance;
- нормализует представление, не объявляя его «истиной»;
- выполняет Entity Resolution;
- обнаруживает конфликты;
- показывает evidence и версии правил;
- оставляет business Decision человеку;
- позже использует подтверждённые Decisions как корпоративную память.

Ключевой принцип: **минимизировать число ситуаций, где человеку действительно нужно принимать решение**.

---

## Слайд 3. Сквозной продуктовый workflow

```text
Import
→ Raw + provenance
→ Normalization
→ Matching / Entity Resolution
→ Conflict Engine
→ Human Review
→ Decision Registry
→ Similar Decision Retrieval
→ Deterministic Recommendation
→ optional AI explanation
→ следующий похожий случай
```

Граница текущей реализации:

- Stage 0–5: ACCEPTED;
- Stage 5: ACCEPTED, OPEN conflicts/Basis/provenance; не Decision Registry;
- Stage 5.1: отдельное обновление оформления существующего Web Client; [галерея реальных экранов](../../frontend/public/interface/index.html), [публикация страницы](../site/interface.md). Будущие функции не изображаются работающими; старый внешний домен ещё не обновлён.
- Stage 6+: pending.

Важно:

- Matching подтверждает identity, но не выбирает истинное значение;
- Conflict обнаруживает проблему, но не создаёт Decision;
- Recommendation не является Decision;
- AI не является памятью или business authority.

---

## Слайд 4. Что уже работает в `main`

### Stage 0 — Infrastructure

- Python 3.13 / FastAPI;
- React / TypeScript / Vite;
- PostgreSQL 17 + pgvector;
- Redis / RQ;
- Docker Compose;
- GitHub Actions CI.

### Stage 1 — Auth / RBAC

- browser login;
- VIEWER / REVIEWER / DATA_OWNER / ADMIN;
- ADMIN не наследует business-review authority.

### Stage 2 — Import

- CSV / XLSX / XML;
- immutable raw;
- file checksum;
- provenance;
- recovery/idempotency.

### Stage 3 — Normalization

- versioned profiles;
- raw + normalized values;
- units/dates/decimal/string normalization;
- provenance/history.

### Stage 4 — Matching

- MATCHED / POSSIBLE_MATCH / NOT_MATCHED;
- exact / rule / fuzzy evidence;
- bounded candidate generation;
- manual identity review;
- final merge `bea0d55c92540744657feac863084cde131a7f43`;
- CI merge commit SUCCESS;
- independent retest PASS;
- 619 automated tests PASS;
- false merges on gold benchmark: 0.

---

## Слайд 5. Stage 5 — Conflict Engine

Полное ТЗ: [issue #21](https://github.com/SergeyRassohin/Forest-Keeper/issues/21).

Минимальные типы:

- `VALUE_MISMATCH`;
- `MISSING`;
- `DUPLICATE`;
- `RULE_VIOLATION`;
- `ANOMALY`.

В принятом Stage 5 генерируются VALUE_MISMATCH/MISSING/DUPLICATE. RULE_VIOLATION/ANOMALY остаются canonical enum с выключенной генерацией до валидных versioned Rules/detector. LOW — нейтральный technical default, не бизнес-риск.

Граница:

- `Conflict != Decision`;
- Stage 5 не выбирает «истинное» значение;
- нет Human Review actions по разрешению;
- нет Decision Registry;
- нет Recommendation;
- нет AI inference.

`RULE_VIOLATION` создаётся только по явному versioned rule source. `ANOMALY` допустим только при воспроизводимом detector; LLM и «магический confidence» не являются доказательством.

---

## Слайд 6. Память и адаптация

Корпоративная память Forest Keeper:

- Decision Registry;
- structured context;
- rules/templates;
- mappings;
- provenance;
- audit;
- embeddings/pgvector для поиска похожих подтверждённых случаев.

Loop:

```text
new conflict
→ similar confirmed Decisions
→ deterministic recommendation
→ AI explanation of supplied evidence
→ human Decision
→ Decision Registry
→ next similar case
```

Qwen не «переобучается после клика» и не является system of record.

---

## Слайд 7. Forest Codex

**Forest Codex** — пользовательское имя версионированного customer baseline.

- FK поставляет baseline template;
- клиент может менять структуру/правила;
- версия имеет собственный ID;
- результаты и решения сохраняют связь с точной версией;
- старая версия архивируется, а не стирается;
- возможен rollback;
- исторический результат должен оставаться воспроизводимым.

Пользовательский контекст должен быть виден явно, например: **Forest Codex v5**.

---

## Слайд 8. Развёртывание и безопасность

Текущее направление клиента: **Web Client only**. Desktop Client исключён из продукта.

```text
Browser
→ HTTPS
→ FK Gateway / API
→ backend / workers / PostgreSQL / storage / audit
```

MVP:

- читает выгрузки клиента;
- пишет только во внутреннее хранилище Forest Keeper;
- не выполняет production write-back;
- AI не имеет production credentials.

Будущая поставка:

- on-prem/private/offline;
- License Service;
- online или signed offline `forestkeeper.license`;
- signed update packages;
- backup → migration → health check → rollback.

---

## Слайд 9. CI / GitHub workflow

В репозитории один workflow: `.github/workflows/ci.yml`, имя **MVP foundation**.

Triggers:

- `push`;
- `pull_request`.

Последовательность:

```text
checkout
→ secret scan
→ Python / uv
→ Node / npm
→ Chromium
→ scripts/check.sh
→ SAST
→ negative security gates
→ dependency audit
→ dev-init
→ Docker Compose
→ integration
→ production smoke
→ logs on failure
→ cleanup always
```

Stage gate:

```text
branch / PR
→ self-review
→ tests + security
→ independent retest
→ Architecture / Product Intent Gate
→ green CI final HEAD
→ explicit owner approval
→ merge
→ green CI exact merge commit
→ ACCEPTED
```

Старые красные runs остаются историей конкретных commit SHA и не означают, что текущий `main` неисправен.

---

## Слайд 10. Ближайшая цель

Внешний специалист без устных подсказок должен пройти:

```text
fresh clone
→ setup
→ ADMIN bootstrap
→ Web Client
→ own CSV/XLSX/XML
→ normalization
→ matching
→ evidence/provenance
→ Conflict
→ Human Review
→ Decision
→ restart
→ same Decision
→ similar case
→ retrieval
→ recommendation
→ optional Qwen explanation
```

На текущем `main` доступны этапы до Conflict Engine включительно. Human Review / Decision Registry — следующий необходимый вертикальный шаг.

Критерий успеха внешней проверки: специалист оценивает продукт, архитектуру, UX, риски и потенциал, а не тратит время на выяснение «как это вообще запустить».

---

## Синхронизация

Обязательные связанные источники:

- [README](../../README.md)
- [workflow overview](../architecture/workflow-overview.md)
- [MVP progress](../development/mvp-progress.md)
- [external review readiness](../deployment/review-readiness.md)
- [Stage 5 issue #21](https://github.com/SergeyRassohin/Forest-Keeper/issues/21)
- [cross-stage issue #20](https://github.com/SergeyRassohin/Forest-Keeper/issues/20)
- [external review issue #18](https://github.com/SergeyRassohin/Forest-Keeper/issues/18)
