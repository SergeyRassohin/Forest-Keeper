# Forest Keeper — Architecture v0.2

## 1. Общий принцип

Forest Keeper — серверная корпоративная система с защищённым клиентским доступом.

Архитектура делится на:
- клиентский слой;
- сервер Forest Keeper;
- внутренние сервисы обработки данных;
- хранилища;
- AI/Recommendation контур;
- лицензирование;
- обновление;
- интеграции с системами заказчика.

Для MVP логические компоненты не обязаны быть отдельными микросервисами. Их можно реализовать как модули одного backend-приложения и разделять физически только по мере необходимости.

## 2. Клиентский слой

Поддерживаются два варианта:

### Desktop Client
Основной вариант для предприятий с жёсткими требованиями ИБ.

- устанавливается централизованно только на разрешённые рабочие станции;
- подключается к FK Server по защищённому каналу;
- может использовать клиентский сертификат устройства;
- пользователь дополнительно проходит идентификацию;
- desktop-клиент не имеет прямого доступа к БД и внутренним сервисам.

### Web Client
Допустимый вариант для организаций, где корпоративная политика разрешает веб-доступ.

Backend/API не должен зависеть от конкретного клиента.

## 3. Серверный контур

Основные компоненты:

- API Gateway;
- Authentication / Authorization;
- License Service;
- Update Service;
- Backend / Application Service;
- Source Adapters;
- Raw Data Storage;
- Normalization Engine;
- Canonical Data Model;
- Matching / Entity Resolution Engine;
- Rules & Conflict Engine;
- Decision Registry;
- Similarity / Embedding Engine;
- Recommendation Engine;
- AI / LLM Service;
- Audit Log;
- PostgreSQL;
- File/Object Storage;
- Background Jobs / Queue.

## 4. Основной поток данных

```mermaid
flowchart LR
    EXT[1C / Excel / CSV / XML / CRM] --> AD[Source Adapters]
    AD --> RAW[Raw Data Storage]
    AD --> NORM[Normalization Engine]
    NORM --> CAN[Canonical Model]
    CAN --> MATCH[Matching / Entity Resolution]
    MATCH --> CONFLICT[Rules & Conflict Engine]
    CONFLICT --> REVIEW[Human Review]
    REVIEW --> DEC[Decision Registry]
    DEC --> SIM[Similarity / Embedding Engine]
    SIM --> REC[Recommendation Engine]
    REC --> AI[AI / LLM Service]
    AI --> REVIEW
    CONFLICT --> AUDIT[Audit Log]
    REVIEW --> AUDIT
```

## 5. Адаптивная модель

Ключевая особенность FK:

```
Базовый шаблон FK
        ↓
Настройки клиента
        ↓
Анализ данных
        ↓
Решение пользователя
        ↓
Decision Registry
        ↓
Поиск похожих решений
        ↓
AI/Recommendation
        ↓
Новая рекомендация
        ↓
Предложение изменить правило/шаблон
        ↓
Human Approval
        ↓
Настроенная модель клиента
```

FK не должен автоматически менять правила после каждого решения.

Если одинаковая практика повторяется, система может предложить:
«В похожих случаях вы систематически выбираете это правило. Закрепить его в настройках?»

Только после подтверждения человека изменение становится формальным правилом клиента.

## 6. AI / LLM

AI — не декоративный компонент.

Его назначение:
- анализировать контекст нового случая;
- использовать найденные похожие подтверждённые решения;
- формировать объяснимую рекомендацию;
- объяснять, на каком прошлом опыте основана рекомендация;
- помогать выявлять устойчивые паттерны поведения клиента.

AI не является корпоративной памятью.

Память находится в:
- Decision Registry;
- правилах;
- mappings;
- master/canonical model;
- Audit.

AI не имеет production credentials и не пишет напрямую в системы заказчика.

## 7. Форматы обмена

### Клиент ↔ Server
HTTPS + JSON DTO.

### Внутренние API
По умолчанию JSON через HTTP/REST или внутренние вызовы модулей для монолита MVP.

### Внешние источники
- 1C XML;
- XLSX;
- CSV;
- JSON;
- API JSON/XML при наличии интеграции.

### DB
SQL через драйвер PostgreSQL.

### AI
Структурированный JSON request/response.

Большие исходные файлы передаются в файловое/object storage, а между компонентами передаётся ID/ссылка на объект, а не копия файла.

## 8. Лицензирование

License Service — серверный компонент FK.

Он проверяет:
- цифровую подпись лицензии;
- клиента;
- срок действия;
- редакцию;
- модули;
- ограничения;
- срок поддержки;
- optional installation/server binding.

Поддерживаются:
- online activation/renewal;
- offline signed license file.

## 9. Обновления

Update Service поддерживает:
- online update;
- offline signed update package;
- проверку подписи;
- проверку совместимости;
- backup;
- migration;
- health check;
- rollback.

## 10. Deployment

Рекомендуемый способ:
- контейнеризированные серверные компоненты;
- один корпоративный installer скрывает внутреннюю Docker/container механику;
- поддержка полностью offline установки в закрытом контуре.

## 11. Trust boundary

```mermaid
flowchart LR
    PC[Trusted workstation] -->|mTLS/HTTPS| GW[FK Gateway]
    USER[User identity] --> AUTH[Auth/RBAC]
    GW --> AUTH
    AUTH --> API[FK API]
    API --> CORE[FK Core]
    CORE --> DB[(PostgreSQL)]
    CORE --> FS[(File Storage)]
    CORE --> AI[AI/LLM]
    CORE --> LIC[License Service]
    CORE --> UPD[Update Service]
    AI -. no production credentials .-> EXT[Customer production systems]
```

## 12. Ключевые ограничения MVP

- source systems read-only;
- no autonomous production write;
- human final decision;
- AI recommendation must be explainable;
- unknown truth remains UNKNOWN / NEEDS_REVIEW;
- customer data remains accessible to customer even when license expires, subject to configured read-only/grace behavior.
