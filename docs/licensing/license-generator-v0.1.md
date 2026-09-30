# Forest Keeper — FK License Generator v0.1

## 1. Назначение

FK License Generator — отдельная внутренняя служебная утилита поставщика Forest Keeper.

Она **не устанавливается заказчику** и не входит в клиентский дистрибутив.

Назначение утилиты:
- создать новую лицензию;
- продлить существующую лицензию;
- изменить редакцию/модули/лимиты;
- привязать лицензию к конкретной установке, если такая политика будет выбрана;
- сформировать подписанный файл `forestkeeper.license`;
- вести внутренний журнал выпущенных лицензий.

## 2. Где используется

```
Поставщик Forest Keeper
        ↓
FK License Generator
        ↓
forestkeeper.license
        ↓
Администратор заказчика
        ↓
FK License Service
```

## 3. Основные поля лицензии

Минимальный набор:

- `license_id`;
- customer legal name;
- customer internal ID / optional tax ID;
- product edition;
- allowed modules;
- valid_from;
- valid_until;
- support_until;
- user/node/installation limits, если применяются;
- installation_id / server binding, если включено;
- issue_date;
- issuer;
- schema_version.

## 4. Формат лицензии

Рекомендуемый подход:

1. сформировать структурированный payload в JSON;
2. сериализовать его канонически;
3. подписать payload закрытым ключом поставщика;
4. сохранить payload + signature в контейнер лицензии `forestkeeper.license`.

Пример логической структуры:

```json
{
  "payload": {
    "license_id": "FK-2026-000123",
    "customer": "ООО Ромашка",
    "edition": "Enterprise",
    "valid_from": "2026-10-01",
    "valid_until": "2027-09-30",
    "support_until": "2027-09-30",
    "modules": [
      "core",
      "entity-resolution",
      "recommendations"
    ],
    "limits": {
      "users": 50
    },
    "installation_id": null,
    "schema_version": 1
  },
  "signature": "BASE64_SIGNATURE"
}
```

## 5. Криптографическая модель

У поставщика:
- private signing key;
- FK License Generator;
- защищённое хранение ключа.

У заказчика:
- только public verification key;
- FK License Service.

Правило:
**закрытый ключ никогда не поставляется клиенту и не хранится в репозитории.**

## 6. Предпочтительная криптография

Для подписи лицензии использовать современную асимметричную цифровую подпись, например Ed25519 или другой утверждённый алгоритм в зависимости от требований конкретного рынка/заказчика.

Конкретный алгоритм фиксируется отдельным security decision до реализации.

## 7. Интерфейс утилиты

На первом этапе достаточно небольшой desktop-утилиты для поставщика.

Экран должен содержать:
- данные заказчика;
- редакцию продукта;
- список модулей;
- срок лицензии;
- срок поддержки;
- ограничения;
- optional installation ID;
- кнопку Generate;
- кнопку Renew existing license;
- preview payload;
- результат проверки подписи;
- путь сохранения файла.

## 8. Продление лицензии

Продление выполняется без переустановки Forest Keeper.

Процесс:

```
открыть существующую лицензию
→ загрузить её параметры
→ изменить valid_until / support_until / modules / limits
→ выпустить новый signed license file
→ передать заказчику
```

## 9. Внутренний журнал лицензий

License Generator должен сохранять внутренний реестр выпущенных лицензий:

- license_id;
- customer;
- issue date;
- validity;
- edition;
- modules;
- status;
- superseded/revoked state;
- hash выпущенного файла.

Журнал нужен для поддержки, продления и расследования спорных случаев.

## 10. Безопасность

- private key не хранится в исходном коде;
- private key не коммитится в Git;
- доступ к генератору ограничен;
- журнал действий сохраняется;
- каждая лицензия имеет уникальный ID;
- файл лицензии должен проверяться самим Generator перед выдачей;
- желательно хранить ключ в OS key store / HSM / защищённом secret store по мере зрелости продукта.

## 11. Не входит в v0.1

На первом этапе не обязательны:
- облачный licensing portal;
- автоматическая биллинговая интеграция;
- сложная revocation infrastructure;
- multi-tenant SaaS licensing.

Сначала достаточно надёжного offline-first выпуска и проверки подписанных license-файлов.
