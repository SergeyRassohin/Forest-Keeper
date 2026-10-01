# Forest Keeper — Client Access Model v0.1

## Основной принцип
Backend и API Forest Keeper не должны зависеть от типа пользовательского клиента.

## Web Client — основной клиент MVP

Основной пользовательский интерфейс Forest Keeper работает в корпоративном браузере.

- React/TypeScript;
- HTTPS через API Gateway;
- RBAC и серверная авторизация;
- browser policies и network restrictions;
- поддержка закрытого контура без обязательного Интернета;
- нет прямого доступа к PostgreSQL или внутренним сервисам.

## Desktop Client — опциональный будущий вариант

Desktop-клиент может быть добавлен для заказчиков с особыми требованиями ИБ:
- централизованная установка только на разрешённые ПК;
- device certificate / mTLS;
- дополнительный контроль доверенного устройства.

Наличие desktop-клиента само по себе не является security boundary. Он использует тот же серверный API и не входит в обязательный состав MVP.

## Двухфакторная логика доверия

```
доверенное устройство
→ защищённый канал
→ идентификация пользователя
→ FK role/RBAC
→ разрешённые операции
```

Device trust и user identity — разные проверки.

## DTO
Клиент получает прикладные JSON DTO:
- entity;
- conflict;
- recommendation;
- provenance;
- available actions.

Клиент не должен напрямую читать PostgreSQL или внутренние raw storage.
