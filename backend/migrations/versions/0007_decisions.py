"""Immutable human decisions, scoped access and atomic Conflict lifecycle."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_decisions"
down_revision = "0006_conflicts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("data_domains", JSONB(), nullable=False, server_default="[]"))
    # Preserve explicit legacy instance-wide data access; new accounts deny by default.
    op.execute("UPDATE users SET data_domains='[\"*\"]'::jsonb")
    op.create_check_constraint(
        "ck_user_domains_array", "users", "jsonb_typeof(data_domains)='array'"
    )
    op.add_column(
        "conflicts", sa.Column("review_version", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("conflicts", sa.Column("current_decision_id", sa.Uuid(), nullable=True))
    op.create_check_constraint("ck_conflict_review_version", "conflicts", "review_version >= 0")
    op.create_table(
        "decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conflict_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), sa.ForeignKey("canonical_entities.id"), nullable=False),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("business_key", sa.String(256), nullable=False),
        sa.Column("attribute_code", sa.String(64), nullable=False),
        sa.Column("decision_type", sa.String(32), nullable=False),
        sa.Column("selected_value", JSONB(), nullable=False),
        sa.Column("selected_source_id", sa.Uuid(), sa.ForeignKey("source_systems.id")),
        sa.Column("selected_value_id", sa.Uuid(), sa.ForeignKey("entity_values.id")),
        sa.Column("value_kind", sa.String(32)),
        sa.Column("unit", sa.String(32)),
        sa.Column("corrected_input", JSONB(), nullable=False),
        sa.Column("conversion_trace", JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_roles", JSONB(), nullable=False),
        sa.Column("actor_display_name", sa.String(200), nullable=False),
        sa.Column(
            "decided_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("context_snapshot", JSONB(), nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.Column("context_version", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("supersedes_decision_id", sa.Uuid()),
        sa.Column("audit_event_id", sa.Uuid(), sa.ForeignKey("audit_events.id"), nullable=False),
        sa.ForeignKeyConstraint(["conflict_id"], ["conflicts.id"]),
        sa.ForeignKeyConstraint(
            ["conflict_id", "supersedes_decision_id"],
            ["decisions.conflict_id", "decisions.id"],
            name="fk_decision_predecessor",
        ),
        sa.UniqueConstraint("conflict_id", "id", name="uq_decision_conflict_id"),
        sa.UniqueConstraint("user_id", "conflict_id", "idempotency_key", name="uq_decision_retry"),
        sa.UniqueConstraint("supersedes_decision_id", name="uq_decision_successor"),
        sa.CheckConstraint(
            "decision_type IN ('SELECT_VALUE','ENTER_VALUE','INSUFFICIENT_DATA','DEFERRED')"
        ),
        sa.CheckConstraint("supersedes_decision_id IS NULL OR supersedes_decision_id <> id"),
        sa.CheckConstraint("char_length(btrim(reason)) BETWEEN 1 AND 2000"),
        sa.CheckConstraint("schema_version = 1"),
        sa.CheckConstraint(
            """
        (decision_type IN ('SELECT_VALUE','ENTER_VALUE') AND
        jsonb_typeof(selected_value)='string' AND value_kind IS NOT NULL) OR (decision_type
        IN ('INSUFFICIENT_DATA','DEFERRED') AND selected_value='null'::jsonb AND
        selected_source_id IS NULL AND selected_value_id IS NULL AND value_kind IS NULL AND
        unit IS NULL)
        """
        ),
        sa.CheckConstraint(
            """
        (decision_type='SELECT_VALUE' AND selected_source_id IS NOT NULL AND
        selected_value_id IS NOT NULL) OR (decision_type<>'SELECT_VALUE' AND
        selected_source_id IS NULL AND selected_value_id IS NULL)
        """
        ),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_decision_first ON decisions(conflict_id) WHERE
        supersedes_decision_id IS NULL
        """
    )
    for name, columns in [
        ("ix_decision_created", ["decided_at", "id"]),
        ("ix_decision_conflict_history", ["conflict_id", "decided_at", "id"]),
        ("ix_decision_domain_created", ["domain", "decided_at", "id"]),
        ("ix_decision_attribute_created", ["attribute_code", "decided_at", "id"]),
        ("ix_decision_actor_created", ["user_id", "decided_at", "id"]),
    ]:
        op.create_index(name, "decisions", columns)
    op.create_foreign_key(
        "fk_conflict_effective_decision",
        "conflicts",
        "decisions",
        ["id", "current_decision_id"],
        ["conflict_id", "id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.execute("""
        CREATE TRIGGER decisions_append_only BEFORE UPDATE OR DELETE ON decisions
        FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()
    """)
    op.execute("""
        
        CREATE FUNCTION guard_decision_insert() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE current_head UUID; current_status TEXT; snapshots JSONB;
        BEGIN
        SELECT current_decision_id,status,values_snapshot INTO
        current_head,current_status,snapshots
        FROM conflicts WHERE id=NEW.conflict_id FOR UPDATE;
        IF NOT FOUND OR current_status <> 'IN_REVIEW' THEN
        RAISE EXCEPTION 'Decision requires persisted human review';
        END IF;
        IF NEW.supersedes_decision_id IS DISTINCT FROM current_head THEN
        RAISE EXCEPTION 'Decision predecessor must be the effective head';
        END IF;
        IF NEW.supersedes_decision_id IS NOT NULL AND NOT EXISTS
        (SELECT 1 FROM decisions WHERE id=NEW.supersedes_decision_id AND
        conflict_id=NEW.conflict_id)
        THEN RAISE EXCEPTION 'Predecessor must already exist in this case'; END IF;
        IF NEW.decision_type='SELECT_VALUE' AND NOT EXISTS (
        SELECT 1 FROM jsonb_array_elements(snapshots) AS side WHERE
        side->>'source_id'=NEW.selected_source_id::text AND
        side->'value'->>'value_id'=NEW.selected_value_id::text AND
        side->'value'->'normalized_value'=NEW.selected_value AND
        side->'value'->>'kind'=NEW.value_kind AND
        (side->'value'->>'unit') IS NOT DISTINCT FROM NEW.unit AND
        side->'value'->>'quality_status'='VALID' AND side->>'presence'='PRESENT'
        ) THEN RAISE EXCEPTION 'Selected value must belong to this Conflict'; END IF;
        RETURN NEW;
        END $$
        
        """)
    op.execute(
        """
        CREATE TRIGGER decision_insert_guard BEFORE INSERT ON decisions FOR EACH ROW EXECUTE
        FUNCTION guard_decision_insert()
        """
    )
    op.execute("DROP TRIGGER conflicts_append_only ON conflicts")
    op.execute("""
        
        CREATE FUNCTION guard_conflict_review() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Conflict history is immutable'; END IF;
        IF (to_jsonb(NEW)-ARRAY['status','review_version','current_decision_id']) IS DISTINCT
        FROM
        (to_jsonb(OLD)-ARRAY['status','review_version','current_decision_id'])
        THEN RAISE EXCEPTION 'Conflict evidence is immutable'; END IF;
        IF NEW.review_version <> OLD.review_version+1 THEN
        RAISE EXCEPTION 'Conflict review requires a new version'; END IF;
        IF NEW.current_decision_id IS NOT DISTINCT FROM OLD.current_decision_id THEN
        IF NEW.status <> 'IN_REVIEW' OR OLD.status='IN_REVIEW' THEN
        RAISE EXCEPTION 'Only explicit review start may precede a Decision'; END IF;
        ELSIF NEW.current_decision_id IS NULL THEN
        RAISE EXCEPTION 'An effective Decision cannot be removed';
        END IF;
        RETURN NEW;
        END $$
        
        """)
    op.execute(
        """
        CREATE TRIGGER conflicts_review_guard BEFORE UPDATE OR DELETE ON conflicts FOR EACH
        ROW EXECUTE FUNCTION guard_conflict_review()
        """
    )
    op.execute("""
        
        CREATE FUNCTION check_conflict_decision_head() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE case_id UUID; state TEXT; head UUID; kind TEXT; latest UUID;
        BEGIN
        IF TG_TABLE_NAME='decisions' THEN case_id:=NEW.conflict_id; ELSE case_id:=NEW.id; END
        IF;
        SELECT status,current_decision_id INTO state,head FROM conflicts WHERE id=case_id;
        SELECT d.id INTO latest FROM decisions d WHERE d.conflict_id=case_id AND NOT EXISTS
        (SELECT 1 FROM decisions next WHERE next.supersedes_decision_id=d.id);
        IF head IS DISTINCT FROM latest THEN RAISE EXCEPTION 'Conflict must reference the
        effective Decision'; END IF;
        IF head IS NOT NULL THEN SELECT decision_type INTO kind FROM decisions WHERE id=head;
        END IF;
        IF (state='OPEN' AND head IS NOT NULL) OR
        (state='RESOLVED' AND (head IS NULL OR kind NOT IN ('SELECT_VALUE','ENTER_VALUE')))
        OR
        (state='INSUFFICIENT_DATA' AND (head IS NULL OR kind <> 'INSUFFICIENT_DATA'))
        THEN RAISE EXCEPTION 'Conflict status requires a matching confirmed Decision'; END
        IF;
        IF TG_TABLE_NAME='decisions' AND NEW.id=head THEN
          IF (kind IN ('SELECT_VALUE','ENTER_VALUE') AND state<>'RESOLVED') OR
             (kind='INSUFFICIENT_DATA' AND state<>'INSUFFICIENT_DATA') OR
             (kind='DEFERRED' AND state<>'IN_REVIEW')
          THEN RAISE EXCEPTION 'New Decision requires its atomic lifecycle result';
          END IF;
        END IF;
        RETURN NULL;
        END $$
        
        """)
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER decision_head_integrity AFTER INSERT ON decisions
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION
        check_conflict_decision_head()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER conflict_head_integrity AFTER INSERT OR UPDATE ON conflicts
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION
        check_conflict_decision_head()
        """
    )


def downgrade() -> None:
    # A schema rollback must never silently erase confirmed business history.
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM decisions)")).scalar():
        raise RuntimeError(
            "Decision history exists: restore a verified backup instead of destructive downgrade"
        )
    op.execute("DROP TRIGGER conflict_head_integrity ON conflicts")
    op.execute("DROP TRIGGER conflicts_review_guard ON conflicts")
    op.drop_constraint("fk_conflict_effective_decision", "conflicts", type_="foreignkey")
    op.drop_table("decisions")
    for function in [
        "guard_decision_insert",
        "guard_conflict_review",
        "check_conflict_decision_head",
    ]:
        op.execute(f"DROP FUNCTION {function}()")
    op.execute(
        """
        CREATE TRIGGER conflicts_append_only BEFORE UPDATE OR DELETE ON conflicts FOR EACH
        ROW EXECUTE FUNCTION reject_audit_mutation()
        """
    )
    op.drop_constraint("ck_conflict_review_version", "conflicts", type_="check")
    op.drop_column("conflicts", "current_decision_id")
    op.drop_column("conflicts", "review_version")
    op.drop_constraint("ck_user_domains_array", "users", type_="check")
    op.drop_column("users", "data_domains")
