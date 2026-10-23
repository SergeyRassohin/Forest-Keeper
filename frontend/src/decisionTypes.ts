export type Decision = {
  id: string; conflict_id: string; entity_id: string; business_key: string;
  attribute_code: string; domain: string; decision_type: string; status: string;
  selected_value: unknown; unit: string | null; selected_source_id: string | null;
  reason: string; actor_display_name?: string; user_id: string; actor_roles: string[]; decided_at: string;
  supersedes_decision_id: string | null; superseded_by: string | null;
  context_snapshot?: unknown; evidence_hash?: string; context_version?: string;
  corrected_input?: unknown; conversion_trace?: unknown;
};
export type ReviewContext = {
  conflict_id: string; conflict_status: string; context_version: string; review_version: number;
  evidence_hash: string; allowed_actions: string[]; can_start_review: boolean; can_supersede: boolean;
  current_decision: Decision | null; history_count: number;
  correction_policy: { allowed: boolean; kind: string | null; unit: string | null; max_length: number };
  selectable_values: { source_id: string; source_name: string; side: string; value_id: string; value: string; unit: string | null }[];
  known_unknowns: { source_id: string; presence: string; quality: string }[];
};
export type Receipt = { decision_id: string; conflict_id: string; conflict_status: string;
  current_conflict_status: string; current_decision_id: string; decision: Decision; message: string };
export const outcomeLabels = new Map(Object.entries({
  SELECT_VALUE: 'Выбрано значение источника', ENTER_VALUE: 'Указано другое значение',
  INSUFFICIENT_DATA: 'Недостаточно данных', DEFERRED: 'Рассмотрение отложено',
}));
