# Forest Keeper — Interface v0.1

## General principle
Forest Keeper is not a task tracker. The main screen should answer: **what is happening with the company's data now?**

The interface must keep a consistent shell for all roles while changing available content and actions according to permissions.

## Authorization screen
Default user flow:
- Forest Keeper logo and system name;
- login field;
- password field;
- password visibility control;
- Sign In button;
- corporate SSO entry point when configured.

Administrative access should not be mixed into the normal form as another field. Use a separate, unobtrusive `Administrator login` path with stronger controls such as MFA, separate policy, logging and optional external-access restrictions.

## Header after sign-in
Show:
- full user name;
- corporate position/title;
- FK role separately from job title;
- avatar or initials;
- profile/settings/logout menu.

Example distinction:
`Иванов Иван Иванович · Руководитель группы внедрения`
`FK role: DATA_OWNER`

Job title and permissions are separate concepts.

## Main navigation
Baseline sections:
- Главная
- Данные
- Проблемы
- Решения
- Аналитика
- Аудит

For ADMIN additionally:
- Администрирование
  - Пользователи
  - Источники
  - Модель данных
  - Маппинг атрибутов
  - Правила
  - Настройки

## Main screen
The main screen is a data-state dashboard, not a list of assigned tasks.

Recommended blocks:
1. Overall Data Health.
2. Number of controlled entities.
3. Number of detected conflicts.
4. Rule violations and anomalies.
5. Cases requiring human review.
6. State by data domain, for example Materials, Products, Contractors, Warehouse.
7. Recent significant events, not an exhaustive event stream.

## Human Review screen
For a conflict, show:
- entity identity;
- conflicting attribute;
- values by source;
- source provenance;
- normalization applied;
- relevant prior confirmed decisions;
- Forest Keeper recommendation and its basis;
- confidence/evidence;
- actions: accept recommendation, choose source value, enter another value, insufficient information;
- optional explanation/comment.

## Website / portal history
An earlier public Forest Keeper website concept used:
- multi-page structure;
- forest background across pages;
- readable, consistent typography;
- polished page transitions;
- separate protected `/service` and `/edit` areas;
- a Project Portal concept for project materials and internal work.

These visual decisions belong to the presentation layer and must not override usability in the operational FK application.
