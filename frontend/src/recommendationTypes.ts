export type RecommendationResult = {
  embedding_model?: { provider?: string; model_id?: string } | null;
  conflict_id: string; status: 'RECOMMENDED' | 'ABSTAINED' | 'UNAVAILABLE';
  recommended_action: 'SELECT_VALUE' | null; recommended_source_id: string | null;
  recommended_value_id: string | null; recommended_value: { kind: string; value: string; unit: string | null } | null;
  confidence: number | null; confidence_unit: 'INDEPENDENT_PROVENANCE_GROUPS'; confidence_label: string;
  reason_code: string; reasoning_summary: string; limitations: string[];
  evidence_summary: { independent_groups?: number; evaluated_precedents?: number; minimum_groups?: number };
  quality_provenance: 'DEMONSTRATION_ONLY' | 'NOT_AVAILABLE';
  evidence: { decision_id: string; actor_display_name: string; decided_at: string; outcome: string;
    reason: string; selected_value: unknown; unit: string | null; logical_role: string | null;
    context_summary: { subject?: string; attribute_code?: string; unit?: string };
    source_correspondence: { historical_source_id: string; current_source_id: string; logical_role: string }[] }[];
  supporting_decision_ids: string[]; conflicting_evidence: string[];
  authority_reference: 'NOT_DEFINED'; rules_status: 'NOT_CONFIGURED'; template_status: 'NOT_CONFIGURED';
  recommendation_policy_version: string; recommendation_policy_hash: string;
  source_mapping_version: string | null; retrieval_version: string | null;
  context_fingerprint: string; review_context_version: string; generated_at: string; audit_reference: string | null;
};
