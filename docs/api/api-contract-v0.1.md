# Forest Keeper — API Contract v0.1

Статус: рабочий контракт для MVP.

## 1. Зачем этот документ

API — это договорённость между браузерным интерфейсом Forest Keeper и сервером.

Пользователь нажимает кнопку в браузере, frontend отправляет запрос серверу, сервер выполняет действие и возвращает структурированный ответ.

Для MVP API должен поддержать первый полный сценарий:

**файл → импорт → анализ → конфликт → решение человека → сохранённый прецедент → рекомендация при похожем случае.**

---

## 2. Общие правила

- Транспорт: HTTPS.
- Формат данных: JSON.
- Версия API: `/api/v1`.
- Идентификаторы сущностей: UUID.
- Даты и время: ISO 8601.
- Файлы загружаются через `multipart/form-data`.
- Все изменения данных журналируются.
- AI/LLM не пишет напрямую в мастер-данные и внешние системы.
- Любое финальное решение по конфликту подтверждает человек.
- Ошибки возвращаются в едином формате.

Пример ошибки:

```json
{
  "error": {
    "code": "CONFLICT_NOT_FOUND",
    "message": "Конфликт не найден",
    "details": {}
  }
}
```

---

## 3. Авторизация

### POST /api/v1/auth/login

Вход пользователя.

Запрос:

```json
{
  "login": "sergey",
  "password": "********"
}
```

Ответ:

```json
{
  "access_token": "...",
  "user": {
    "id": "uuid",
    "display_name": "Сергей",
    "roles": ["DATA_OWNER"]
  }
}
```

### GET /api/v1/auth/me

Возвращает текущего пользователя и его роли.

---

## 4. Источники данных

### GET /api/v1/sources

Список настроенных источников.

### POST /api/v1/sources

Создать источник.

Пример:

```json
{
  "code": "one_c_main",
  "name": "1С основная",
  "source_type": "ONE_C"
}
```

### GET /api/v1/sources/{source_id}

Карточка источника.

### PATCH /api/v1/sources/{source_id}

Изменение настроек источника.

---

## 5. Импорт файлов

### POST /api/v1/imports

Загрузить файл и создать пакет импорта.

Параметры:

- `source_id`
- файл

Ответ:

```json
{
  "import_batch_id": "uuid",
  "status": "NEW",
  "file_name": "materials.xlsx"
}
```

### GET /api/v1/imports/{import_batch_id}

Статус импорта.

Ответ:

```json
{
  "id": "uuid",
  "status": "COMPLETED",
  "records_total": 1542,
  "records_loaded": 1542,
  "records_failed": 0
}
```

### GET /api/v1/imports/{import_batch_id}/errors

Ошибки разбора файла.

---

## 6. Запуск анализа

### POST /api/v1/analysis

Запустить нормализацию, сопоставление и поиск конфликтов по выбранным пакетам или источникам.

Запрос:

```json
{
  "import_batch_ids": ["uuid-1", "uuid-2"],
  "template_id": "uuid"
}
```

Ответ:

```json
{
  "analysis_id": "uuid",
  "status": "PROCESSING"
}
```

### GET /api/v1/analysis/{analysis_id}

Статус анализа.

Ответ:

```json
{
  "id": "uuid",
  "status": "COMPLETED",
  "matches_found": 320,
  "conflicts_found": 47
}
```

---

## 7. Конфликты

### GET /api/v1/conflicts

Список конфликтов.

Поддерживаемые фильтры:

- `status`
- `severity`
- `conflict_type`
- `entity_type`
- `source_id`
- `page`
- `page_size`

Пример ответа:

```json
{
  "items": [
    {
      "id": "uuid",
      "entity_type": "Material",
      "attribute_code": "mass",
      "conflict_type": "VALUE_MISMATCH",
      "severity": "MEDIUM",
      "status": "OPEN"
    }
  ],
  "total": 47
}
```

### GET /api/v1/conflicts/{conflict_id}

Полная карточка конфликта.

Ответ должен содержать:

- сравниваемые записи;
- исходные значения;
- нормализованные значения;
- источник каждого значения;
- применённые правила;
- найденные похожие решения;
- текущую рекомендацию FK.

Пример:

```json
{
  "id": "uuid",
  "entity": {
    "id": "uuid",
    "entity_type": "Material"
  },
  "attribute_code": "mass",
  "values": [
    {
      "source": "1С",
      "raw_value": "12.5",
      "normalized_value": "12.5"
    },
    {
      "source": "Excel legacy",
      "raw_value": "12,7 кг",
      "normalized_value": "12.7"
    }
  ],
  "recommendation_id": "uuid"
}
```

---

## 8. Решение пользователя

### POST /api/v1/conflicts/{conflict_id}/decisions

Пользователь фиксирует решение.

Пример:

```json
{
  "decision_type": "SELECT_VALUE",
  "selected_value": "12.5",
  "comment": "Для массы этого типа материала считаем 1С доверенным источником"
}
```

Сервер обязан:

1. сохранить решение;
2. сохранить контекст конфликта на момент решения;
3. записать пользователя и время;
4. изменить статус конфликта;
5. добавить решение в историю прецедентов;
6. создать событие аудита.

Ответ:

```json
{
  "decision_id": "uuid",
  "conflict_status": "RESOLVED"
}
```

### GET /api/v1/conflicts/{conflict_id}/decisions

История решений по конфликту.

---

## 9. Рекомендации Forest Keeper

### GET /api/v1/conflicts/{conflict_id}/recommendation

Получить рекомендацию для текущего конфликта.

Ответ:

```json
{
  "id": "uuid",
  "recommended_action": {
    "decision_type": "SELECT_VALUE",
    "selected_value": "12.5"
  },
  "confidence": 0.86,
  "reasoning_summary": "В 8 похожих подтверждённых случаях пользователь выбирал значение из 1С.",
  "similar_decisions": [
    {
      "decision_id": "uuid",
      "similarity": 0.93
    }
  ],
  "rules_used": [
    "material_mass_source_priority"
  ]
}
```

Ключевой принцип: рекомендация не считается решением и ничего не меняет без подтверждения человека.

---

## 10. Похожие прошлые решения

### GET /api/v1/conflicts/{conflict_id}/similar-decisions

Возвращает подтверждённые ранее решения, наиболее похожие на текущий случай.

Параметры:

- `limit`
- `min_similarity`

Ответ:

```json
{
  "items": [
    {
      "decision_id": "uuid",
      "similarity": 0.93,
      "summary": "Для массы материала выбран источник 1С",
      "created_at": "2026-09-10T09:30:00Z"
    }
  ]
}
```

---

## 11. Правила

### GET /api/v1/rules

Список действующих правил.

### POST /api/v1/rules

Создать правило вручную.

### PATCH /api/v1/rules/{rule_id}

Изменить правило.

### POST /api/v1/rules/{rule_id}/activate

Активировать правило.

### POST /api/v1/rules/{rule_id}/deactivate

Отключить правило.

---

## 12. Предложение нового правила на основе истории решений

### GET /api/v1/rule-suggestions

Список закономерностей, которые Forest Keeper предлагает превратить в формальное правило.

Пример:

```json
{
  "items": [
    {
      "id": "uuid",
      "summary": "В 12 из 12 похожих случаев для атрибута mass выбиралось значение из 1С",
      "suggested_rule": {
        "entity_type": "Material",
        "attribute_code": "mass",
        "preferred_source": "one_c_main"
      }
    }
  ]
}
```

### POST /api/v1/rule-suggestions/{suggestion_id}/accept

Человек подтверждает создание правила.

### POST /api/v1/rule-suggestions/{suggestion_id}/reject

Человек отклоняет предложение.

Forest Keeper не должен активировать новое правило без подтверждения пользователя.

---

## 13. Шаблон заказчика

### GET /api/v1/templates/current

Получить текущий шаблон клиента.

### PATCH /api/v1/templates/current

Изменить настройки шаблона.

### POST /api/v1/templates/current/reset

Вернуться к базовому шаблону FK.

Перед сбросом требуется явное подтверждение пользователя.

---

## 14. Канонические сущности

### GET /api/v1/entities

Поиск и список канонических сущностей.

### GET /api/v1/entities/{entity_id}

Карточка сущности с атрибутами и provenance.

### GET /api/v1/entities/{entity_id}/history

История изменений и подтверждений.

---

## 15. Аудит

### GET /api/v1/audit

Журнал действий.

Фильтры:

- пользователь;
- тип события;
- объект;
- период.

Аудит должен позволять восстановить, кто, когда и на основании чего изменил состояние данных или правил.

---

## 16. Системная информация

### GET /api/v1/health

Техническая проверка доступности сервера.

### GET /api/v1/version

Версия Forest Keeper.

### GET /api/v1/license

Текущее состояние лицензии без раскрытия служебных секретов.

Пример:

```json
{
  "edition": "Enterprise",
  "valid_until": "2027-10-01",
  "modules": ["IMPORT", "MATCHING", "RECOMMENDATIONS"],
  "status": "VALID"
}
```

---

## 17. Что не входит в API v0.1

Пока не фиксируем окончательно:

- прямую запись данных обратно в 1С/ERP/PLM;
- автоматическое изменение корпоративных мастер-данных;
- сложные массовые workflow согласования;
- внешние публичные API для партнёров;
- обучение собственной нейросети после каждого решения;
- vendor-specific интеграционные контракты.

Это будет добавляться после первого рабочего вертикального сценария.

---

## 18. Минимальный набор endpoint'ов для первого вертикального прототипа

Чтобы начать разработку, достаточно реализовать сначала только:

1. `POST /api/v1/imports`
2. `GET /api/v1/imports/{id}`
3. `POST /api/v1/analysis`
4. `GET /api/v1/conflicts`
5. `GET /api/v1/conflicts/{id}`
6. `POST /api/v1/conflicts/{id}/decisions`
7. `GET /api/v1/conflicts/{id}/recommendation`
8. `GET /api/v1/conflicts/{id}/similar-decisions`

Если этот набор работает от начала до конца, Forest Keeper уже умеет выполнить основную идею MVP, а не просто гордо содержать папку `docs`.
