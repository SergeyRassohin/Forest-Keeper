# Forest Keeper — Product Roadmap v0.1

Статус: стратегический roadmap развития продукта.

Основание: docs/project-context.md, docs/architecture/architecture-v0.2.md, docs/development/mvp-development-plan-v0.1.md, docs/decisions/decision-log.md.

## 1. Назначение

MVP Development Plan отвечает на вопрос «в каком порядке реализовать MVP».

Этот roadmap отвечает на другой вопрос:

**Во что должен последовательно превратиться Forest Keeper как продукт, чтобы не потерять исходный замысел по дороге от прототипа к промышленному решению?**

Roadmap фиксирует продуктовые уровни зрелости, а не обещанные календарные даты. Переход между уровнями выполняется только после stage gate: проверка соответствия замыслу + архитектуре + техническая приёмка.

---

## 2. Неизменяемое ядро продукта

Во всех последующих версиях Forest Keeper сохраняет следующие принципы:

1. FK — надстройка над ERP/PLM/PDM/MDM/WMS/CRM/1С/Excel, а не их замена.
2. Raw и provenance сохраняются.
3. Canonical representation нужна для сопоставления, но не объявляется абсолютной истиной.
4. Если истина не определима безопасно, результат — UNKNOWN / Human Review.
5. Человек принимает финальное бизнес-решение.
6. AI/LLM объясняет и рекомендует, но не является system of record.
7. Корпоративная память находится в Decision Registry, Rules, Customer Template / Gold Reference, mappings и Audit.
8. Gold Reference версионируется, изменяется только через явное подтверждение человека и имеет историю, rollback и impact analysis.
9. Source systems в ранних режимах read-only.
10. Любой future write-back отделён технически и организационно от анализа.
11. Любой значимый derived result должен быть воспроизводим по версиям входных данных, правил, Gold Reference и алгоритмов.
12. Продукт должен работать в закрытом контуре без обязательного Интернета.

---

## 3. Лестница зрелости Forest Keeper

Prototype
→ Observer
→ Advisor
→ Adaptive Advisor
→ Enterprise Pilot
→ Production 1.0
→ Post-check / Continuous Data Health
→ Controlled Gateway
→ Controlled Publication

Каждая следующая ступень расширяет полномочия системы, но не отменяет human-in-the-loop и историческую воспроизводимость.

---

## 4. Фаза A — Prototype 0.1

### Цель

Доказать полный цикл:

два источника → raw → normalization → matching → conflict → recommendation → human decision → Decision Registry → следующий похожий случай использует прошлое решение.

### Уже реализовано

**Stage 0 — Foundation**
- FastAPI;
- React/TypeScript;
- PostgreSQL + pgvector;
- Redis/RQ;
- Docker/HTTPS;
- migrations/testing/CI.

**Stage 1 — Authentication + RBAC**
- локальная аутентификация;
- server-side sessions;
- роли/permissions;
- backend authorization;
- audit security events.

**Stage 2 — Sources & Import**
- SourceSystem;
- ImportBatch;
- RawRecord;
- CSV/XLSX/XML/синтетический 1С XML;
- checksum;
- immutable original;
- provenance;
- RQ processing.

**Stage 3 — Normalization / Canonical pre-match representation**
- CanonicalEntity pre-match;
- EntityValue;
- versioned mappings;
- strings/dates/decimal/units;
- raw + normalized;
- quality status;
- provenance;
- recovery/idempotency.

### Следующие MVP stages

**Stage 4 — Matching / Entity Resolution**
- exact/rule/fuzzy matching;
- explainable MatchCandidate;
- false-merge protection;
- gold benchmark;
- approved thresholds.

**Stage 5 — Conflict Engine**
- выявление расхождений;
- evidence;
- severity;
- связи с source values.

**Stage 6 — Human Review**
- полноценная карточка случая;
- сравнение источников;
- review через Web Client.

**Stage 7 — Decision Registry**
- immutable human decisions;
- actor/time/reason/context;
- восстановление исторического контекста.

**Stage 8 — Similarity**
- поиск похожих подтверждённых решений;
- pgvector + deterministic filtering;
- explainable top-N.

**Stage 9 — Recommendation Engine**
- recommendation на основе rules + history;
- confidence/evidence;
- graceful degradation без AI.

**Stage 10 — Local AI / LLM Provider**
- локальный Qwen baseline;
- объяснение и анализ;
- structured output;
- deterministic fallback;
- отсутствие production credentials.

**Stage 11 — Rules / Customer Template / Gold Reference**
- базовый шаблон FK;
- customer-specific rules;
- versioning;
- Gold Reference history;
- activation;
- impact analysis;
- stale/re-evaluation framework;
- rollback через новую версию.

**Stage 12 — Rule Suggestions**
- повторяющиеся решения → предложение формализовать;
- human approval;
- никакого silent self-learning.

**Stage 13 — Full Audit**
Полная трасса:
Source → Import → Raw → Normalization → Match → Conflict → Recommendation → Decision → Rule/Gold Reference version.

**Stage 14 — Licensing**
- offline license;
- signature validation;
- ACTIVE / GRACE_PERIOD / READ_ONLY;
- данные клиента остаются доступны.

**Stage 15 — Update Service**
- signed package;
- backup;
- migration;
- health;
- rollback;
- offline-first.

**Stage 16 — Final MVP E2E**
Две последовательные итерации одного сценария. Во второй FK должен использовать подтверждённое решение из первой.

### Exit criteria Prototype 0.1

Прототип закрывается только если:
- второй похожий случай обрабатывается умнее первого за счёт подтверждённой истории;
- пользователь понимает, почему FK предлагает действие;
- исходные системы не изменяются;
- весь путь воспроизводим через Audit;
- architecture/product-intent gate пройден.

---

## 5. Фаза B — Pilot Ready

### Цель

Перейти от синтетических профилей к реальным данным и рабочему сценарию предприятия.

### 5.1. Выбрать первый pilot domain

Явно выбрать:
- домен;
- entity types;
- business keys;
- атрибуты;
- единицы;
- обязательные поля;
- правила качества;
- Authoritative Source policy.

### 5.2. Реальный 1С/Excel profile
- реальные экспортные примеры;
- проверка совместимости;
- customer mappings;
- fixture anonymization;
- validation against pilot data.

### 5.3. Gold Reference bootstrap
- supplier baseline;
- customer adaptations;
- version 1;
- signed-off scope.

### 5.4. Data Health dashboard

Главный экран должен перейти от infrastructure-health к состоянию данных:
- matched/unmatched;
- conflicts;
- quality issues;
- stale results;
- cases requiring review;
- Gold Reference changes;
- significant events.

### 5.5. Pilot operations
- backup/restore;
- export;
- log retention;
- offline installation;
- update dry-run;
- admin runbook;
- diagnostics bundle без утечки данных.

### 5.6. Security pilot gate
- DAST;
- fuzz/property;
- threat-model review;
- independent security review;
- dependency/license review;
- installation hardening.

### Exit criteria Pilot Ready

FK можно поставить в изолированную тестовую среду заказчика и воспроизводимо выполнить согласованный бизнес-сценарий на реальных обезличенных или контролируемых данных.

---

## 6. Фаза C — Forest Keeper 1.0: Observer + Advisor

### Observer
FK читает источники и показывает состояние данных, не изменяя production systems.

### Advisor
FK:
- объясняет проблему;
- показывает доказательства;
- учитывает исторические решения;
- формирует рекомендацию;
- человек принимает решение.

### Ключевые возможности 1.0
- стабильная установка;
- offline-first;
- licensing;
- update;
- real domain templates;
- versioned Gold Reference;
- Decision Registry;
- matching/conflicts/recommendations;
- Data Health;
- Audit/export;
- RBAC;
- customer configuration;
- rollback Gold Reference;
- impact analysis;
- stale/re-evaluation;
- локальный AI как заменяемый помощник.

### Что не входит автоматически
- write-back;
- blocking gateway;
- silent correction;
- autonomous rule mutation;
- broad ERP connector zoo.

---

## 7. Фаза D — Adaptive Advisor 1.x

### Цель

Сделать накопленный опыт заказчика реальной корпоративной памятью.

### Decision intelligence
- richer case context;
- более точный similarity;
- decision clustering;
- explainable precedents;
- выявление противоречивых решений экспертов.

### Gold Reference evolution
- история версий;
- visual diff;
- impact graph;
- re-evaluation queue;
- stale markers;
- rollback;
- proposal based on stable decision patterns;
- review before activation.

### Human variability controls

Поскольку экспертные решения могут быть ситуативными, ошибочными или эмоциональными:
- одно решение не меняет Gold;
- противоречивые решения выявляются;
- тренд учитывает выборку, период и scope;
- proposal показывает evidence;
- изменение reference требует отдельного approval;
- прошлое не переписывается.

### Rule governance
- draft → review → approved;
- scope;
- effective-from;
- supersedes;
- reason;
- audit.

### Explainability
Пользователь может ответить:
- почему такой match;
- почему такой conflict;
- почему такая recommendation;
- какие решения повлияли;
- какая версия Gold Reference применялась.

---

## 8. Фаза E — Enterprise scale

### Multi-domain
- Material;
- Supplier;
- Equipment;
- Product;
- Customer;
- другие customer templates.

### Более широкий ingestion
- JSON;
- REST read connectors;
- scheduled file ingestion;
- SFTP/file shares;
- DB read adapters;
- configurable connector SDK.

### Enterprise identity
После отдельного решения:
- AD/LDAP/OIDC/SAML;
- SSO;
- group mapping.

### Operations
- central diagnostics;
- metrics;
- alerting;
- backup policies;
- HA where justified;
- scale testing;
- storage lifecycle.

### Governance
- scoped roles;
- domain ownership;
- separation of duties;
- optional Four Eyes for critical changes;
- change approval.

### Security
- independent pentest;
- SBOM;
- signed artifacts;
- supply-chain controls;
- hardened offline distribution.

---

## 9. Фаза F — Post-check / Continuous Data Health

### Цель

FK работает постоянно, а не только по ручной загрузке.

### Возможности
- scheduled ingestion;
- incremental analysis;
- trend monitoring;
- quality drift;
- source drift;
- Gold Reference drift impact;
- new conflict detection;
- regression against historical baseline;
- alerts;
- Data Health timeline.

FK по-прежнему не обязан вмешиваться в источник.

---

## 10. Фаза G — Controlled Gateway

Для выбранных критичных потоков FK может давать:
- PASS;
- WARNING;
- REVIEW.

PASS означает только, что FK не нашёл причины блокировать операцию по текущим правилам.

До включения нужны:
- зрелые rules;
- measured false-positive/false-negative rates;
- SLA;
- fail-safe behavior;
- operational bypass;
- full audit;
- explicit customer approval.

Gateway не должен автоматически становиться Publisher.

---

## 11. Фаза H — Controlled Publication / Publisher

Опциональный write-back только после отдельного зрелого этапа.

### Архитектурные требования
- Reader identity и Publisher identity разделены;
- AI никогда не получает Publisher credentials;
- publication payload формируется из подтверждённого решения;
- allowlisted target operations;
- approval;
- idempotency;
- dry-run;
- rollback/compensation where possible;
- audit;
- target-system acknowledgment.

Это отдельный уровень риска и не входит в ранний MVP.

---

## 12. Сквозное направление — Gold Reference

Gold Reference должен развиваться вместе с организацией.

Vendor baseline
→ Customer baseline v1
→ Human decisions
→ Pattern detected
→ RuleSuggestion
→ Review
→ Approved new Gold Reference version
→ Impact analysis
→ Re-evaluation / stale marking
→ Possible rollback as another version

Обязательные свойства:
- append-only versions;
- immutable history;
- current active pointer;
- structured diff;
- reason/actor;
- linked decisions;
- impact scope;
- rollback;
- reproducible historical evaluation.

---

## 13. Сквозное направление — AI maturity

**Уровень 0:** AI отсутствует. Детерминированный pipeline работает.

**Уровень 1:** AI объясняет структурированные evidence.

**Уровень 2:** AI помогает обобщить похожие решения и контекст.

**Уровень 3:** AI предлагает формализацию повторяющейся практики.

Запрещено AI самостоятельно:
- объявлять истину;
- менять Gold Reference;
- активировать Rules;
- принимать business Decision;
- писать в production.

---

## 14. Сквозное направление — UI maturity

### MVP
Import / Normalize / Match / Conflict / Review.

### 1.0
Data Health-first control panel.

### 1.x
- impact analysis;
- Gold Reference history/diff;
- stale/re-evaluate;
- decision precedents.

### Enterprise
- domain dashboards;
- system health + data health;
- governance;
- trends;
- alerts.

Интерфейс не должен превращаться в generic task tracker.

---

## 15. Сквозное направление — коммерческая зрелость

### Prototype
Доказать гипотезу.

### Pilot
Доказать ценность на одном реальном домене.

### 1.0
Повторяемая установка и понятный коммерческий пакет.

### Repeatable deployment
- installer;
- licensing;
- update;
- baseline templates;
- implementation guide;
- support model.

### Expansion
- дополнительные domain packs;
- connector packs;
- enterprise security/SSO;
- optional Gateway/Publisher modules.

---

## 16. Что сознательно не надо делать слишком рано

- Kubernetes «потому что enterprise»;
- Kafka без подтверждённой нагрузки;
- отдельная vector DB при рабочем pgvector;
- десятки коннекторов до доказанного pilot domain;
- микросервисы ради диаграммы;
- mobile app;
- autonomous write-back;
- красивый AI-chat вместо Decision Registry;
- silent self-learning;
- hard-coded immutable Gold Reference.

---

## 17. Product stage gate перед каждой фазой

Перед переходом ответить:

1. Соответствует ли реализация исходному замыслу?
2. Не стал ли derived результат случайно «истиной»?
3. Сохраняются ли raw/provenance?
4. Сохраняется ли human final authority?
5. Можно ли воспроизвести результат исторически?
6. Сохраняется ли версия Gold Reference/rules/mappings/algorithms?
7. Можно ли определить impact их изменения?
8. Есть ли stale/re-evaluation path?
9. Не появился ли скрытый write-back?
10. Не стал ли AI критической точкой отказа или власти?
11. Документация соответствует фактическому main?
12. Есть ли измеримая пользовательская ценность нового уровня?

Если критический ответ «нет», переход блокируется независимо от количества зелёных тестов.

---

## 18. Ближайший практический порядок

На текущем состоянии проекта:

1. Stage 4 — Matching / Entity Resolution.
2. Stage 5 — Conflict Engine.
3. Stage 6 — Human Review UI.
4. Stage 7 — Decision Registry.
5. Stage 8 — Similarity.
6. Stage 9 — Recommendation.
7. Stage 10 — Local AI provider.
8. Stage 11–12 — Rules / Customer Template / evolving Gold Reference.
9. Stage 13 — complete Audit.
10. Stage 14–15 — Licensing + Update.
11. Stage 16 — Final MVP E2E.
12. Выбор реального pilot domain.
13. Pilot-ready hardening.
14. Первый controlled pilot.
15. Forest Keeper 1.0 Observer + Advisor.

---

## 19. Главный продуктовый критерий

Forest Keeper развивается правильно, если со временем он:
- лучше понимает контекст клиента;
- использует подтверждённую историю решений;
- умеет объяснить свои выводы;
- показывает влияние изменения правил/эталона;
- сохраняет прошлое;
- позволяет людям менять мнение без разрушения истории;
- становится полезнее, но не получает неограниченную власть над данными.

**Forest Keeper должен накапливать организационный опыт, а не накапливать самоуверенность алгоритма.**
