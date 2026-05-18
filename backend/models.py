from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, DateTime, Text, Float, UniqueConstraint
from .database import Base


class UniversalEntity(Base):
    __tablename__ = "raw_entities"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    import_batch_id = Column(Integer, ForeignKey("import_batches.id"), nullable=True, index=True)

    # Universal fields
    domain = Column(String, default="default", index=True)
    entity_type = Column(String, nullable=True, index=True)

    primary_label = Column(String, index=True)
    secondary_label = Column(String, nullable=True)
    canonical_id = Column(String, index=True, nullable=True)

    attributes_json = Column(Text, default="{}")

    # Metadata
    validation_status = Column(String, default="pending", index=True)
    normalized_json = Column(Text, nullable=True)

    # Enrichment
    enrichment_doi = Column(String, nullable=True)
    enrichment_citation_count = Column(Integer, default=0)
    enrichment_concepts = Column(Text, nullable=True)
    enrichment_source = Column(String, nullable=True)
    enrichment_status = Column(String, default="none", index=True)

    # Sprint 72 — Quality Score
    quality_score = Column(Float, nullable=True, index=True)

    # Engine sync
    updated_at = Column(DateTime, nullable=True)

    # Provenance
    source = Column(String, default="user")

# Keep alias so existing imports of models.RawEntity still work
RawEntity = UniversalEntity


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id          = Column(Integer, primary_key=True, index=True)
    org_id      = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    source_id   = Column(Integer, ForeignKey("raw_entities.id"), index=True)
    target_id   = Column(Integer, ForeignKey("raw_entities.id"), index=True)
    relation_type = Column(String, index=True)  # cites | authored-by | belongs-to | related-to
    weight      = Column(Float, default=1.0)
    notes       = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class NormalizationRule(Base):
    __tablename__ = "normalization_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    field_name = Column(String, index=True) # e.g., "brand_lower"
    original_value = Column(String, index=True) # e.g., "mikrosoft"
    canonical_value = Column(String) # e.g., "Microsoft"
    rule_type = Column(String, default="exact")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def normalized_value(self):
        return self.canonical_value

    @normalized_value.setter
    def normalized_value(self, value):
        self.canonical_value = value

    @property
    def is_regex(self):
        return self.rule_type == "regex"

    @is_regex.setter
    def is_regex(self, value):
        self.rule_type = "regex" if value else "exact"


class HarmonizationLog(Base):
    __tablename__ = "harmonization_logs"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    step_id = Column(String, index=True)
    step_name = Column(String)
    records_updated = Column(Integer)
    fields_modified = Column(Text)
    executed_at = Column(DateTime)
    details = Column(Text, nullable=True)
    reverted = Column(Boolean, default=False)


class HarmonizationChangeRecord(Base):
    __tablename__ = "harmonization_change_records"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(Integer, ForeignKey("harmonization_logs.id"), index=True)
    record_id = Column(Integer, ForeignKey("raw_entities.id"), index=True)
    field = Column(String)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)


class StoreConnection(Base):
    __tablename__ = "store_connections"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    name = Column(String, index=True)                    # Human-friendly label, e.g. "Mi Tienda WooCommerce"
    platform = Column(String, index=True)                # woocommerce | shopify | bsale | custom
    base_url = Column(String)                            # e.g. https://mitienda.com
    api_key = Column(String, nullable=True)               # Consumer key / API key
    api_secret = Column(String, nullable=True)            # Consumer secret / API secret
    access_token = Column(String, nullable=True)          # For OAuth-based platforms (Shopify)
    custom_headers = Column(Text, nullable=True)          # JSON string for custom API headers
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime)
    entity_count = Column(Integer, default=0)            # Cached count of mapped products
    sync_direction = Column(String, default="bidirectional")  # pull | push | bidirectional
    notes = Column(Text, nullable=True)


class StoreSyncMapping(Base):
    __tablename__ = "store_sync_mappings"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, index=True)               # FK to store_connections.id
    local_entity_id = Column(Integer, index=True)       # FK to raw_entities.id
    remote_entity_id = Column(String, nullable=True)    # ID in the remote store
    canonical_url = Column(String, index=True)            # The canonical URL used for mapping
    remote_sku = Column(String, nullable=True)
    remote_name = Column(String, nullable=True)
    remote_price = Column(String, nullable=True)
    remote_stock = Column(String, nullable=True)
    remote_status = Column(String, nullable=True)
    remote_data_json = Column(Text, nullable=True)       # Full remote product data snapshot
    sync_status = Column(String, default="pending")      # pending | synced | conflict | error
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime)


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, index=True)               # FK to store_connections.id
    action = Column(String)                              # pull | push | map | unmap
    status = Column(String)                              # success | error | partial
    records_affected = Column(Integer, default=0)
    details = Column(Text, nullable=True)                # JSON with details
    executed_at = Column(DateTime)


class SyncQueueItem(Base):
    __tablename__ = "sync_queue"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, index=True)               # FK to store_connections.id
    mapping_id = Column(Integer, nullable=True, index=True)  # FK to store_sync_mappings.id
    direction = Column(String)                            # pull | push
    entity_name = Column(String, nullable=True)          # For display convenience
    canonical_url = Column(String, nullable=True)
    field = Column(String)                                # Which field changed
    local_value = Column(Text, nullable=True)
    remote_value = Column(Text, nullable=True)
    status = Column(String, default="pending", index=True) # pending | approved | rejected | applied
    created_at = Column(DateTime)
    resolved_at = Column(DateTime, nullable=True)

class AIIntegration(Base):
    """
    Phase 5: Store settings for Semantic RAG architectures (LLMs and Vector DBs).
    Supports Cloud (OpenAI, Claude, DeepSeek, XAI, Google) and Local variants.
    """
    __tablename__ = "ai_integrations"

    id = Column(Integer, primary_key=True, index=True)
    provider_name = Column(String, index=True, unique=True)  # openai | anthropic | xai | deepseek | google | local
    base_url = Column(String, nullable=True)                 # for local/custom endpoints
    api_key = Column(String, nullable=True)                  # Bring Your Own Key (BYOK)
    model_name = Column(String, nullable=True)               # e.g., gpt-4o, claude-3.5-sonnet, r1, llama3
    is_active = Column(Boolean, default=False)               # which provider is the active one?
    created_at = Column(DateTime)


# ── RBAC: Users ────────────────────────────────────────────────────────────

class User(Base):
    """
    Platform user with a fixed role (super_admin | admin | editor | viewer).
    Credentials are stored in this table; no more env-var-only auth.
    """
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, index=True, nullable=False)
    email           = Column(String(255), unique=True, index=True, nullable=True)
    password_hash   = Column(String, nullable=False)
    role            = Column(String, nullable=False, default="viewer")
    is_active       = Column(Boolean, default=True)
    created_at      = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    failed_attempts = Column(Integer, default=0)
    locked_until    = Column(String, nullable=True)  # ISO datetime string; None = not locked
    avatar_url      = Column(Text, nullable=True)       # data URL (base64), Sprint 58
    display_name    = Column(String(100), nullable=True)  # optional full name, Sprint 59
    bio             = Column(Text, nullable=True)          # short bio, Sprint 59
    org_id          = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at    = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Authority Resolution Layer ──────────────────────────────────────────────

class AuthorityRecord(Base):
    """
    Stores candidates returned by the Authority Resolution Layer.
    Each record links a local field value to an entry in an external
    knowledge authority (Wikidata, VIAF, ORCID, DBpedia, OpenAlex).
    status: pending | confirmed | rejected
    """
    __tablename__ = "authority_records"

    id               = Column(Integer, primary_key=True, index=True)
    org_id           = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    field_name       = Column(String, index=True)         # e.g. "brand_capitalized"
    original_value   = Column(String, index=True)         # local value that was queried
    authority_source = Column(String, index=True)         # wikidata | viaf | orcid | dbpedia | openalex
    authority_id     = Column(String)                     # Q2283 | viaf/20069448 | 0000-0001-… etc.
    canonical_label  = Column(String)                     # official canonical form from the authority
    aliases          = Column(Text, nullable=True)        # JSON array of known aliases
    description      = Column(Text, nullable=True)        # short description from authority
    confidence       = Column(Float, default=0.0)         # 0.0–1.0 fuzzy similarity score
    uri              = Column(String, nullable=True)       # URL of the authority record
    status           = Column(String, default="pending", index=True)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    confirmed_at     = Column(DateTime, nullable=True)
    # Sprint 16 — scoring engine
    resolution_status = Column(String, default="unresolved", index=True)  # exact_match | probable_match | ambiguous | unresolved
    score_breakdown   = Column(Text, nullable=True)   # JSON: {identifiers, name, affiliation, coauthorship, topic}
    evidence          = Column(Text, nullable=True)   # JSON array of signal strings
    merged_sources    = Column(Text, nullable=True)   # JSON array of "source:id" refs merged into this record
    # Sprint 106 - author resolution engine baseline
    resolution_route  = Column(String, nullable=True, index=True)  # fast_path | hybrid_path | llm_path | manual_review
    complexity_score  = Column(Float, nullable=True, index=True)   # 0.0-1.0 complexity heuristic
    review_required   = Column(Boolean, default=False, index=True)
    nil_reason        = Column(String, nullable=True)
    nil_score         = Column(Float, nullable=True, index=True)
    hierarchy_distance = Column(Integer, nullable=True)
    reformulation_applied = Column(Boolean, default=False, index=True)
    reformulation_gain = Column(Integer, nullable=True)
    reformulation_cost_estimate = Column(Float, nullable=True)
    reformulation_trace = Column(Text, nullable=True)


class AuthorityRecordLink(Base):
    """
    Auditable links between authority records.

    Used for external authority relationships that may exist before internal
    RawEntity nodes are confirmed or materialized.
    """
    __tablename__ = "authority_record_links"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    source_authority_record_id = Column(Integer, ForeignKey("authority_records.id"), index=True, nullable=False)
    target_authority_record_id = Column(Integer, ForeignKey("authority_records.id"), index=True, nullable=False)
    link_type = Column(String, index=True)
    confidence = Column(Float, default=0.0)
    status = Column(String, default="pending", index=True)
    evidence = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    confirmed_at = Column(DateTime, nullable=True)


class Webhook(Base):
    """
    Outbound webhook registration.
    events: JSON array of action strings, e.g. ["upload", "entity.delete"]
    secret: optional HMAC-SHA256 signing key sent in X-UKIP-Signature header
    """
    __tablename__ = "webhooks"

    id                = Column(Integer, primary_key=True, index=True)
    url               = Column(String, nullable=False)
    events            = Column(Text, nullable=False)           # JSON array
    secret            = Column(String, nullable=True)
    is_active         = Column(Boolean, default=True)
    created_at        = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_triggered_at = Column(DateTime, nullable=True)
    last_status       = Column(Integer, nullable=True)         # HTTP status of last delivery


class WebhookDelivery(Base):
    """
    Sprint 60: Logs each outbound webhook delivery attempt.
    Enables the delivery history timeline in the Webhooks UI Panel.
    """
    __tablename__ = "webhook_deliveries"

    id          = Column(Integer, primary_key=True, index=True)
    webhook_id  = Column(Integer, index=True, nullable=False)   # FK webhooks.id
    event       = Column(String, nullable=False)                # e.g. "upload", "entity.delete"
    url         = Column(String, nullable=False)                # destination URL at time of delivery
    status_code = Column(Integer, nullable=True)                # HTTP status (0 = network error)
    response_body = Column(Text, nullable=True)                 # first 500 chars of response
    latency_ms  = Column(Integer, nullable=True)                # round-trip time in milliseconds
    error       = Column(String, nullable=True)                 # exception message if delivery failed
    success     = Column(Boolean, default=False)                # True if 2xx
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class LinkDismissal(Base):
    """Stores entity pairs the user has explicitly marked as 'not a duplicate'."""
    __tablename__ = "link_dismissals"

    id          = Column(Integer, primary_key=True, index=True)
    entity_a_id = Column(Integer, index=True, nullable=False)   # always the smaller ID
    entity_b_id = Column(Integer, index=True, nullable=False)   # always the larger ID
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id          = Column(Integer, primary_key=True, index=True)
    action      = Column(String, index=True)          # CREATE | UPDATE | DELETE (Sprint 51+)
    entity_type = Column(String, nullable=True)       # "entity", "authority_record", "rule", …
    entity_id   = Column(Integer, nullable=True)
    user_id     = Column(Integer, nullable=True)
    details     = Column(Text, nullable=True)         # JSON blob with extra context
    # Sprint 51 — HTTP-level columns added via migration
    username    = Column(String, nullable=True, index=True)  # JWT "sub" claim
    endpoint    = Column(String, nullable=True)              # /entities/42
    method      = Column(String, nullable=True)              # POST | PUT | DELETE
    status_code = Column(Integer, nullable=True)
    ip_address  = Column(String, nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# ── Sprint 42: Collaborative Annotations ────────────────────────────────────

class Annotation(Base):
    """
    Threaded comment attached to a RawEntity or AuthorityRecord.
    parent_id enables one-level reply threading.
    author_name is denormalized for display without a JOIN.
    """
    __tablename__ = "annotations"

    id           = Column(Integer, primary_key=True, index=True)
    entity_id    = Column(Integer, nullable=True, index=True)    # FK raw_entities.id
    authority_id = Column(Integer, nullable=True, index=True)    # FK authority_records.id
    parent_id    = Column(Integer, nullable=True)                # FK annotations.id (replies)
    author_id    = Column(Integer, nullable=False)               # FK users.id
    author_name  = Column(String, nullable=False)               # denormalized
    content      = Column(Text, nullable=False)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))
    # Sprint 86 — resolve workflow + emoji reactions
    is_resolved     = Column(Boolean, default=False)
    resolved_at     = Column(DateTime, nullable=True)
    resolved_by_id  = Column(Integer, nullable=True)   # FK users.id
    emoji_reactions = Column(Text, default="{}")        # JSON: {"👍": [uid, ...], "❤️": [...]}


# ── Sprint 43: Email Notification Settings (singleton, id=1) ────────────────

class NotificationSettings(Base):
    __tablename__ = "notification_settings"

    id                         = Column(Integer, primary_key=True, default=1)
    smtp_host                  = Column(String, default="")
    smtp_port                  = Column(Integer, default=587)
    smtp_user                  = Column(String, default="")
    smtp_password              = Column(String, default="")  # stored encrypted via Fernet
    from_email                 = Column(String, default="")
    recipient_email            = Column(String, default="")
    enabled                    = Column(Boolean, default=False)
    notify_on_enrichment_batch = Column(Boolean, default=True)
    notify_on_authority_confirm= Column(Boolean, default=True)


# ── Sprint 44: Custom Branding Settings (singleton, id=1) ───────────────────

class BrandingSettings(Base):
    __tablename__ = "branding_settings"

    id            = Column(Integer, primary_key=True, default=1)
    platform_name = Column(String, default="UKIP")
    logo_url      = Column(String, default="")
    favicon_url   = Column(String, default="")          # custom favicon (ICO/PNG/SVG)
    accent_color  = Column(String, default="#6366f1")   # indigo-500
    footer_text   = Column(String, default="Universal Knowledge Intelligence Platform")


# ── Platform Authentication Settings (singleton, id=1) ──────────────────────

class PlatformAuthSettings(Base):
    __tablename__ = "platform_auth_settings"

    id                       = Column(Integer, primary_key=True, default=1)
    sso_enabled              = Column(Boolean, default=False)
    sso_login_button_visible = Column(Boolean, default=False)
    sso_provider_label       = Column(String, default="SSO")
    sso_auto_provision       = Column(Boolean, default=True)
    sso_default_role         = Column(String, default="viewer")
    sso_allowed_domains      = Column(Text, default="")  # comma-separated email domains


# ── Phase 10 Sprint 46: Artifact Templates ────────────────────────────────────

class ArtifactTemplate(Base):
    """
    Saved report configurations. 4 built-in templates are seeded in lifespan.
    User-created templates have is_builtin=False and can be deleted.
    sections stores a JSON array of section name strings.
    """
    __tablename__ = "artifact_templates"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, nullable=False)
    description   = Column(String, default="")
    sections      = Column(Text, nullable=False)       # JSON: ["entity_stats", ...]
    default_title = Column(String, default="")
    is_builtin    = Column(Boolean, default=False)
    created_by    = Column(Integer, nullable=True)     # FK users.id (nullable for built-ins)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Phase 11 Sprint 48: Analysis Context Sessions ─────────────────────────────

class AnalysisContext(Base):
    """
    Persisted domain context snapshot. Stores the assembled domain state
    (entity stats, gaps, topics, schema) at a point in time.
    Used by the Context Engineering Layer and context-aware RAG.
    """
    __tablename__ = "analysis_contexts"

    id               = Column(Integer, primary_key=True, index=True)
    domain_id        = Column(String, nullable=False, index=True)
    user_id          = Column(Integer, nullable=True)     # FK users.id (nullable for system)
    label            = Column(String, default="")         # user-defined name
    context_snapshot = Column(Text, nullable=False)       # JSON from ContextEngine
    notes            = Column(Text, nullable=True)
    pinned           = Column(Boolean, default=False)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Sprint 56: Notification Center read-state ─────────────────────────────────

class UserNotificationState(Base):
    """
    One row per user tracking when they last read all their notifications.
    last_read_at is used as the threshold: audit log entries created after
    this timestamp are considered "unread".
    """
    __tablename__ = "user_notification_states"

    user_id      = Column(Integer, primary_key=True)   # FK users.id
    last_read_at = Column(DateTime, nullable=True)     # NULL = never read anything


class UserNotificationRead(Base):
    """
    Per-user read overrides for individual notifications newer than last_read_at.
    This keeps the notification centre honest when a user marks a single entry
    as read without clearing the whole backlog.
    """
    __tablename__ = "user_notification_reads"

    user_id = Column(Integer, primary_key=True, index=True)
    audit_log_id = Column(Integer, primary_key=True, index=True)
    read_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Sprint 61: Scheduled Imports ───────────────────────────────────────────────

class ScheduledImport(Base):
    """
    Cron-based automated ingestion from a configured store connection.
    interval_minutes is a simple interval approach (no full cron parser needed).
    """
    __tablename__ = "scheduled_imports"

    id              = Column(Integer, primary_key=True, index=True)
    org_id          = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    store_id        = Column(Integer, index=True, nullable=False)  # FK store_connections.id
    name            = Column(String, nullable=False)               # human label
    interval_minutes = Column(Integer, nullable=False, default=60) # run every N minutes
    is_active       = Column(Boolean, default=True)
    last_run_at     = Column(DateTime, nullable=True)
    next_run_at     = Column(DateTime, nullable=True)
    last_status     = Column(String, nullable=True)               # success | error | running
    last_result     = Column(Text, nullable=True)                 # JSON with result details
    total_runs      = Column(Integer, default=0)
    total_entities_imported = Column(Integer, default=0)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ImportBatch(Base):
    """
    Formal ingestion batch used to trace exactly which records came from one import event.
    Catalog portals can point to a concrete batch for precise discovery scope.
    """
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    domain_id = Column(String(80), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, default="upload", index=True)
    file_name = Column(String(255), nullable=True)
    file_format = Column(String(50), nullable=True)
    source_label = Column(String(200), nullable=True)
    total_rows = Column(Integer, default=0)
    entity_type_hint = Column(String(80), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# ── Sprint 81: Alert Channels (Slack / Teams / Discord / Generic) ─────────────

class AlertChannel(Base):
    """
    Push-notification channel for operational events.
    type: slack | teams | discord | webhook
    events: JSON list of subscribed event names
    webhook_url: encrypted inbound webhook URL
    """
    __tablename__ = "alert_channels"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(200), nullable=False)
    type        = Column(String(20), nullable=False, default="slack")  # slack|teams|discord|webhook
    webhook_url = Column(Text, nullable=False)                          # Fernet-encrypted
    events      = Column(Text, default="[]")                            # JSON list of event names
    is_active   = Column(Boolean, default=True)
    last_fired_at    = Column(DateTime, nullable=True)
    last_fire_status = Column(String(10), nullable=True)                # ok | error
    total_fired      = Column(Integer, default=0)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Sprint 82: API Keys ────────────────────────────────────────────────────────

class ApiKey(Base):
    """
    Long-lived API keys for programmatic access.
    The full key is only shown once at creation time; only a SHA-256 hash is stored.
    key_prefix: first 12 chars (e.g. 'ukip_xYzAbc') — shown in listings for identification.
    scopes: JSON list — 'read', 'write', 'admin'
    """
    __tablename__ = "api_keys"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name         = Column(String(200), nullable=False)
    key_prefix   = Column(String(20), nullable=False)    # e.g. 'ukip_xYzAbcDeFgH'
    key_hash     = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hex
    scopes       = Column(Text, default='["read"]')      # JSON list
    expires_at   = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Sprint 80: Custom Dashboards ──────────────────────────────────────────────

class UserDashboard(Base):
    """
    Per-user custom dashboard: a named collection of widgets with a JSON layout.
    Each user can have multiple dashboards; one can be marked is_default.
    """
    __tablename__ = "user_dashboards"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name       = Column(String(200), nullable=False)
    layout     = Column(Text, default="[]")    # JSON list of WidgetConfig objects
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Sprint 79: Scheduled Reports ──────────────────────────────────────────────

class ScheduledReport(Base):
    """
    Periodic email delivery of generated reports (PDF / Excel / HTML).
    The background scheduler thread checks every 60 s for due reports and
    sends them as email attachments using the NotificationSettings SMTP config.
    """
    __tablename__ = "scheduled_reports"

    id               = Column(Integer, primary_key=True, index=True)
    org_id           = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    name             = Column(String(200), nullable=False)
    domain_id        = Column(String(64), default="default")
    format           = Column(String(10), default="pdf")     # pdf | excel | html
    sections         = Column(Text, default="[]")            # JSON list of section ids
    report_title     = Column(String(200), nullable=True)
    interval_minutes = Column(Integer, nullable=False, default=1440)  # 1440 = daily
    recipient_emails = Column(Text, default="[]")            # JSON list of addresses
    is_active        = Column(Boolean, default=True)
    last_run_at      = Column(DateTime, nullable=True)
    next_run_at      = Column(DateTime, nullable=True)
    last_status      = Column(String(20), default="pending") # pending | success | error
    last_error       = Column(Text, nullable=True)
    total_sent       = Column(Integer, default=0)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Sprint 85: Multi-tenant Organizations ─────────────────────────────────────

class Organization(Base):
    """
    Top-level tenant workspace. Users belong to one or more organizations.
    Data scoped per organization when org_id is set.
    """
    __tablename__ = "organizations"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(200), nullable=False)
    slug        = Column(String(100), nullable=False, unique=True, index=True)  # URL-safe identifier
    description = Column(Text, nullable=True)
    plan        = Column(String(20), default="free")  # free | pro | enterprise
    benchmark_profile_id = Column(String(80), nullable=True)
    benchmark_profile_overrides = Column(Text, default="{}")
    owner_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OrganizationMember(Base):
    """
    Membership link between a User and an Organization.
    role: owner | admin | member
    """
    __tablename__ = "organization_members"

    id          = Column(Integer, primary_key=True, index=True)
    org_id      = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role        = Column(String(20), default="member")  # owner | admin | member
    joined_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CatalogPortal(Base):
    """
    Lightweight discovery portal scoped to an organization and domain.
    Phase A persists domain and saved filters instead of a concrete import batch,
    so we can ship a navigable catalog view before ingestion snapshots exist.
    """
    __tablename__ = "catalog_portals"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    source_batch_id = Column(Integer, ForeignKey("import_batches.id"), nullable=True, index=True)
    domain_id = Column(String(80), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    slug = Column(String(120), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    visibility = Column(String(20), nullable=False, default="private", index=True)  # private | org | public
    source_label = Column(String(200), nullable=True)
    source_context_json = Column(Text, default="{}")
    query_json = Column(Text, default="{}")
    featured_facets_json = Column(Text, default="[]")
    default_sort = Column(String(40), nullable=False, default="primary_label")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Sprint 90: Web Scraper Configs ────────────────────────────────────────────

class WebScraperConfig(Base):
    """
    Configuration for a URL-based enrichment scraper.
    url_template: URL with {primary_label} placeholder (e.g. https://example.com/search?q={primary_label})
    selector_type: css | xpath
    selector: CSS selector or XPath expression to target the data element
    field_map: JSON dict mapping scraped keys to entity field names
    rate_limit_secs: minimum seconds between requests (default 1)
    is_active: if False the scraper is skipped by the enrichment worker
    """
    __tablename__ = "web_scraper_configs"

    id              = Column(Integer, primary_key=True, index=True)
    org_id          = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    name            = Column(String(200), nullable=False)
    url_template    = Column(Text, nullable=False)         # e.g. https://site.com/search?q={primary_label}
    selector_type   = Column(String(10), default="css")   # css | xpath
    selector        = Column(Text, nullable=False)         # CSS selector or XPath expr
    field_map       = Column(Text, default="{}")           # JSON: {"scraped_key": "entity_field"}
    rate_limit_secs = Column(Float, default=1.0)           # min secs between requests
    is_active       = Column(Boolean, default=True, index=True)
    last_run_at     = Column(DateTime, nullable=True)
    last_run_status = Column(String(20), nullable=True)    # ok | error | skipped
    total_runs      = Column(Integer, default=0)
    total_enriched  = Column(Integer, default=0)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Sprint 92: Workflow Automation Engine ──────────────────────────────────────

class Workflow(Base):
    """
    No-code automation workflow: trigger → conditions → actions chain.
    trigger_type: entity.created | entity.enriched | entity.flagged | manual
    conditions:   JSON array of {type, field, operator, value} objects
    actions:      JSON array of {type, config} objects
    """
    __tablename__ = "workflows"

    id           = Column(Integer, primary_key=True, index=True)
    org_id       = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    name         = Column(String(200), nullable=False)
    description  = Column(Text, nullable=True)
    is_active    = Column(Boolean, default=True, index=True)
    trigger_type = Column(String(50), nullable=False, index=True)
    trigger_config = Column(Text, default="{}")   # JSON — extra trigger params
    conditions   = Column(Text, default="[]")     # JSON array of condition objects
    actions      = Column(Text, default="[]")     # JSON array of action objects
    created_by   = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_run_at  = Column(DateTime, nullable=True)
    run_count    = Column(Integer, default=0)
    last_run_status = Column(String(20), nullable=True)  # success | error | skipped


class WorkflowRun(Base):
    """
    Execution log for a single workflow invocation.
    """
    __tablename__ = "workflow_runs"

    id           = Column(Integer, primary_key=True, index=True)
    org_id       = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    workflow_id  = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    status       = Column(String(20), nullable=False, default="running")  # running|success|error|skipped
    trigger_data = Column(Text, default="{}")   # JSON — entity id / event data
    steps_log    = Column(Text, default="[]")   # JSON — per-action results
    error        = Column(Text, nullable=True)
    started_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


# ── Concept Hierarchy (Domain Analysis Fase A) ────────────────────────────────

class ConceptNode(Base):
    """
    Hierarchical concept node materialized from OpenAlex.
    Scoped per domain; self-referential tree via parent_id.
    """
    __tablename__ = "concept_nodes"
    __table_args__ = (
        UniqueConstraint("openalex_id", "domain", name="uq_concept_openalex_domain"),
    )

    id             = Column(Integer, primary_key=True, index=True)
    openalex_id    = Column(String, nullable=False, index=True)
    display_name   = Column(String, nullable=False)
    level          = Column(Integer, nullable=False, default=0)
    parent_id      = Column(Integer, ForeignKey("concept_nodes.id"), nullable=True, index=True)
    entity_count   = Column(Integer, default=0)
    domain         = Column(String, nullable=False, index=True)
    last_fetched_at = Column(DateTime, nullable=True)


# ── Sprint 93: Embed Widgets (Widget SDK) ─────────────────────────────────────

class EmbedWidget(Base):
    """
    Embeddable data widget with a public token.
    widget_type: entity_stats | top_concepts | recent_entities | quality_score
    public_token: UUID — used in the public /embed/{token}/data endpoint (no auth)
    allowed_origins: comma-separated list of allowed embed origins, or "*"
    """
    __tablename__ = "embed_widgets"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(200), nullable=False)
    widget_type     = Column(String(50), nullable=False, index=True)
    config          = Column(Text, default="{}")          # JSON: domain, limit, title, theme, etc.
    public_token    = Column(String(36), unique=True, index=True, nullable=False)
    allowed_origins = Column(Text, default="*")           # "*" or comma-separated origins
    is_active       = Column(Boolean, default=True, index=True)
    view_count      = Column(Integer, default=0)
    created_by      = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_viewed_at  = Column(DateTime, nullable=True)
