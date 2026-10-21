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

## Единственный пользовательский клиент

Desktop Client исключён из направления продукта явным решением от 21 октября 2026 в [Decision Log](../decisions/decision-log.md). Отделение backend/API от frontend не подразумевает будущего native-клиента.

## Границы доверия

```
доверенное устройство
→ защищённый канал
→ идентификация пользователя
→ FK role/RBAC
→ разрешённые операции
```

Device trust и user identity — разные проверки. Схема описывает возможную корпоративную политику, а не реализованный MFA/device-trust в текущем MVP. Текущий вход — локальный пароль и защищённая browser cookie.

## DTO
Клиент получает прикладные JSON DTO:
- entity;
- conflict;
- recommendation;
- provenance;
- available actions.

Клиент не должен напрямую читать PostgreSQL или внутренние raw storage.
