# Forest Keeper — Data Model v0.2

Статус: каноническая модель данных MVP для разработки.

Forest_Keeper_Data_Model_v0.1.xlsx сохранён как исторический черновик. Для реализации использовать этот документ вместе с docs/development/object-lifecycles-v0.1.md и docs/security/access-control-matrix-v0.1.xlsx.

## Общие принципы

- Raw-данные неизменяемы.
- Normalized value не заменяет raw value.
- Canonical representation не является автоматически истиной.
- Provenance обязателен.
- Decision после создания не редактируется задним числом.
- Recommendation не является Decision.
- AI/LLM не является корпоративной памятью.
- Состояния объектов берутся только из Object Lifecycles.
- Права на действия берутся только из Access Control Matrix.

## SourceSystem
Поля: id UUID; name String; code String; source_type Enum; status ACTIVE/DISABLED/ARCHIVED; authority_scope JSON; created_at; updated_at.

## ImportBatch
Поля: id; source_system_id; original_filename; format; file_hash; storage_uri; status; uploaded_by; uploaded_at; error_text.

Канонические состояния:
NEW → QUEUED → PROCESSING → COMPLETED / COMPLETED_WITH_ERRORS / FAILED.

## AnalysisRun
Поля: id; status; import_batch_ids; template_id; created_at; completed_at; error_text.

Канонические состояния:
NEW → QUEUED → PROCESSING → COMPLETED / FAILED.

## RawRecord
Поля: id; import_batch_id; source_record_key; source_object_type; raw_payload; source_position; created_at.

RawRecord является неизменяемым снимком исходной записи.

## CanonicalEntity
Поля: id; domain; entity_type; display_name; status; created_at; updated_at.

## EntityValue
Поля: id; entity_id; attribute_code; raw_record_id; raw_value; normalized_value; unit; quality_status; normalization_rule; created_at.

quality_status: VALID / WARNING / INVALID / UNKNOWN.

## MatchCandidate
Поля: id; raw_record_a_id; raw_record_b_id; confidence; evidence; status; confirmed_by; created_at.

Канонические состояния:
POSSIBLE_MATCH → MATCHED / NOT_MATCHED.

POSSIBLE_MATCH может отображаться в UI как Needs Review, но код состояния в модели один.

## Conflict
Поля: id; entity_id; analysis_run_id; attribute_code; conflict_type; severity; values_snapshot; basis; status; detected_at.

conflict_type:
VALUE_MISMATCH / MISSING / DUPLICATE / RULE_VIOLATION / ANOMALY.

severity:
LOW / MEDIUM / HIGH / CRITICAL.

Канонические состояния:
OPEN → IN_REVIEW → RESOLVED или INSUFFICIENT_DATA.

Новый импорт с похожей проблемой создаёт новый Conflict. Ранее RESOLVED конфликт не переоткрывается для нового случая.

## Recommendation
Поля: id; conflict_id; status; recommended_action; confidence; similar_decision_ids; rules_used; reasoning_summary; model_version; context_snapshot; created_at.

Канонические состояния:
CURRENT → STALE → SUPERSEDED.

Recommendation не имеет состояния ACCEPTED. Согласие пользователя создаёт Decision.

## Decision
Поля: id; conflict_id; status; decision_type; selected_value; selected_source_id; reason; user_id; decided_at; context_snapshot; recommendation_id; supersedes_decision_id.

Канонические состояния:
ACTIVE → SUPERSEDED.

decision_type:
SELECT_VALUE / ENTER_VALUE / INSUFFICIENT_DATA / DEFERRED.

Все записи Decision по определению являются human-confirmed; HUMAN_CONFIRMED не используется как отдельный decision_type.

Decision является append-only бизнес-фактом.

## Rule
Поля: id; code; name; scope; rule_type; definition; origin; status; version; approved_by; effective_from.

origin:
FK_BASELINE / CUSTOMER / LEARNED_PROPOSAL.

Канонические состояния:
DRAFT / ACTIVE / INACTIVE.

Изменение содержания ACTIVE Rule создаёт новую версию.

## RuleSuggestion
Поля: id; status; basis; suggested_rule; decision_ids; created_at; reviewed_by; reviewed_at.

Канонические состояния:
OPEN → ACCEPTED / REJECTED / STALE.

ACCEPTED не означает автоматическую активацию Rule. Дальнейшее действие подчиняется RBAC.

## CustomerTemplate
Поля: id; name; baseline_version; customer_version; definition; status; approved_by; created_at.

Канонические состояния:
DRAFT → ACTIVE → SUPERSEDED.

Одновременно активна ровно одна версия шаблона клиента.

## User и UserRole

User:
id; login; full_name; job_title; status ACTIVE/BLOCKED/DISABLED; created_at.

UserRole:
id; user_id; role_code; assigned_at.

Канонические роли:
VIEWER / REVIEWER / DATA_OWNER / ADMIN.

Должность сотрудника не равна роли FK. Один пользователь может иметь несколько ролей.

## AuditEvent
Поля: id; event_type; user_id; object_type; object_id; payload; created_at.

AuditEvent — append-only запись.

## License state
Канонические состояния runtime-лицензии:
ACTIVE / GRACE_PERIOD / READ_ONLY / INVALID.

INVALID означает провал проверки подписи или содержимого, а не обычное истечение срока.

## Ключевые связи

- SourceSystem 1:N ImportBatch.
- ImportBatch 1:N RawRecord.
- ImportBatch N:M AnalysisRun.
- RawRecord 1:N EntityValue.
- RawRecord N:M RawRecord через MatchCandidate.
- CanonicalEntity 1:N EntityValue.
- AnalysisRun 1:N Conflict.
- CanonicalEntity 1:N Conflict.
- Conflict 1:N Recommendation.
- Conflict 1:N Decision.
- Decision N:M Recommendation как similar historical decisions.
- Decision N:M RuleSuggestion.
- RuleSuggestion 0..1:1 Rule после human approval.
- User 1:N Decision.
- User 1:N UserRole.
- CustomerTemplate 1:N Rule как логическая/версионная связь.
- User/System 1:N AuditEvent.

## Инварианты реализации

1. Conflict нельзя сделать RESOLVED без подтверждённого Decision.
2. INSUFFICIENT_DATA фиксируется и как статус Conflict, и как структурированный Decision.
3. Recommendation не изменяет Rule, Decision или source data.
4. AI не переводит Rule или RuleSuggestion в подтверждённое состояние.
5. RawRecord не переписывается нормализованными значениями.
6. Исторический Decision, Rule, Template и Recommendation сохраняют версию и контекст, использованный в тот момент.
7. Backend валидирует state transition и RBAC независимо от UI.
