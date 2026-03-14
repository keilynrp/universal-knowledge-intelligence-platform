from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float
from .database import Base

import json
from sqlalchemy.ext.hybrid import hybrid_property
import sqlalchemy as sa

class UniversalEntity(Base):
    __tablename__ = "raw_entities"

    id = Column(Integer, primary_key=True, index=True)
    
    # --- Universal Paradigm (Phase 8) ---
    domain = Column(String, default="ecommerce", index=True)  # science, healthcare, business, etc.
    entity_type = Column(String, default="product", index=True) # Type classification
    
    primary_label = Column(String, index=True)      # e.g., product_name, paper title
    secondary_label = Column(String)                # e.g., brand, author
    canonical_id = Column(String, index=True)       # e.g., sku, doi, gtin
    
    attributes_json = Column(Text, default="{}")    # Flexible data schema
    
    # Metadata
    validation_status = Column(String, default="pending", index=True)
    normalized_json = Column(Text, nullable=True)   # Keep for harmonization backward compat

    # Scientometric Enrichment Fields
    enrichment_doi = Column(String, nullable=True)
    enrichment_citation_count = Column(Integer, default=0)
    enrichment_concepts = Column(Text, nullable=True) 
    enrichment_source = Column(String, nullable=True)
    enrichment_status = Column(String, default="none", index=True)

    # Data provenance
    source = Column(String, default="user")

    # =========================================================
    # BACKWARD COMPATIBILITY LAYER (e-commerce legacy fields)
    # =========================================================
    
    @hybrid_property
    def entity_name(self): return self.primary_label
    @entity_name.setter
    def entity_name(self, val): self.primary_label = val
    @entity_name.expression
    def entity_name(cls): return cls.primary_label

    @hybrid_property
    def sku(self): return self.canonical_id
    @sku.setter
    def sku(self, val): self.canonical_id = val
    @sku.expression
    def sku(cls): return cls.canonical_id

    # JSON mappings
    def _get_attr(self, key):
        if not self.attributes_json: return None
        return json.loads(self.attributes_json).get(key)

    def _set_attr(self, key, val):
        d = json.loads(self.attributes_json) if self.attributes_json else {}
        d[key] = val
        self.attributes_json = json.dumps(d)


    @hybrid_property
    def classification(self): return self._get_attr("classification")
    @classification.setter
    def classification(self, val): self._set_attr("classification", val)
    @classification.expression
    def classification(cls): return sa.func.json_extract(cls.attributes_json, '$.classification')

    @hybrid_property
    def is_decimal_sellable(self): return self._get_attr("is_decimal_sellable")
    @is_decimal_sellable.setter
    def is_decimal_sellable(self, val): self._set_attr("is_decimal_sellable", val)
    @is_decimal_sellable.expression
    def is_decimal_sellable(cls): return sa.func.json_extract(cls.attributes_json, '$.is_decimal_sellable')

    @hybrid_property
    def control_stock(self): return self._get_attr("control_stock")
    @control_stock.setter
    def control_stock(self, val): self._set_attr("control_stock", val)
    @control_stock.expression
    def control_stock(cls): return sa.func.json_extract(cls.attributes_json, '$.control_stock')

    @hybrid_property
    def status(self): return self._get_attr("status")
    @status.setter
    def status(self, val): self._set_attr("status", val)
    @status.expression
    def status(cls): return sa.func.json_extract(cls.attributes_json, '$.status')

    @hybrid_property
    def taxes(self): return self._get_attr("taxes")
    @taxes.setter
    def taxes(self, val): self._set_attr("taxes", val)
    @taxes.expression
    def taxes(cls): return sa.func.json_extract(cls.attributes_json, '$.taxes')

    @hybrid_property
    def variant(self): return self._get_attr("variant")
    @variant.setter
    def variant(self, val): self._set_attr("variant", val)
    @variant.expression
    def variant(cls): return sa.func.json_extract(cls.attributes_json, '$.variant')

    @hybrid_property
    def entity_code_universal_1(self): return self._get_attr("entity_code_universal_1")
    @entity_code_universal_1.setter
    def entity_code_universal_1(self, val): self._set_attr("entity_code_universal_1", val)
    @entity_code_universal_1.expression
    def entity_code_universal_1(cls): return sa.func.json_extract(cls.attributes_json, '$.entity_code_universal_1')

    @hybrid_property
    def entity_code_universal_2(self): return self._get_attr("entity_code_universal_2")
    @entity_code_universal_2.setter
    def entity_code_universal_2(self, val): self._set_attr("entity_code_universal_2", val)
    @entity_code_universal_2.expression
    def entity_code_universal_2(cls): return sa.func.json_extract(cls.attributes_json, '$.entity_code_universal_2')

    @hybrid_property
    def entity_code_universal_3(self): return self._get_attr("entity_code_universal_3")
    @entity_code_universal_3.setter
    def entity_code_universal_3(self, val): self._set_attr("entity_code_universal_3", val)
    @entity_code_universal_3.expression
    def entity_code_universal_3(cls): return sa.func.json_extract(cls.attributes_json, '$.entity_code_universal_3')

    @hybrid_property
    def entity_code_universal_4(self): return self._get_attr("entity_code_universal_4")
    @entity_code_universal_4.setter
    def entity_code_universal_4(self, val): self._set_attr("entity_code_universal_4", val)
    @entity_code_universal_4.expression
    def entity_code_universal_4(cls): return sa.func.json_extract(cls.attributes_json, '$.entity_code_universal_4')

    @hybrid_property
    def brand_lower(self): return self._get_attr("brand_lower")
    @brand_lower.setter
    def brand_lower(self, val): self._set_attr("brand_lower", val)
    @brand_lower.expression
    def brand_lower(cls): return sa.func.json_extract(cls.attributes_json, '$.brand_lower')

    @hybrid_property
    def brand_capitalized(self): return self._get_attr("brand_capitalized")
    @brand_capitalized.setter
    def brand_capitalized(self, val): self._set_attr("brand_capitalized", val)
    @brand_capitalized.expression
    def brand_capitalized(cls): return sa.func.json_extract(cls.attributes_json, '$.brand_capitalized')

    @hybrid_property
    def model(self): return self._get_attr("model")
    @model.setter
    def model(self, val): self._set_attr("model", val)
    @model.expression
    def model(cls): return sa.func.json_extract(cls.attributes_json, '$.model')

    @hybrid_property
    def gtin(self): return self._get_attr("gtin")
    @gtin.setter
    def gtin(self, val): self._set_attr("gtin", val)
    @gtin.expression
    def gtin(cls): return sa.func.json_extract(cls.attributes_json, '$.gtin')

    @hybrid_property
    def gtin_reason(self): return self._get_attr("gtin_reason")
    @gtin_reason.setter
    def gtin_reason(self, val): self._set_attr("gtin_reason", val)
    @gtin_reason.expression
    def gtin_reason(cls): return sa.func.json_extract(cls.attributes_json, '$.gtin_reason')

    @hybrid_property
    def gtin_empty_reason_1(self): return self._get_attr("gtin_empty_reason_1")
    @gtin_empty_reason_1.setter
    def gtin_empty_reason_1(self, val): self._set_attr("gtin_empty_reason_1", val)
    @gtin_empty_reason_1.expression
    def gtin_empty_reason_1(cls): return sa.func.json_extract(cls.attributes_json, '$.gtin_empty_reason_1')

    @hybrid_property
    def gtin_empty_reason_2(self): return self._get_attr("gtin_empty_reason_2")
    @gtin_empty_reason_2.setter
    def gtin_empty_reason_2(self, val): self._set_attr("gtin_empty_reason_2", val)
    @gtin_empty_reason_2.expression
    def gtin_empty_reason_2(cls): return sa.func.json_extract(cls.attributes_json, '$.gtin_empty_reason_2')

    @hybrid_property
    def gtin_empty_reason_3(self): return self._get_attr("gtin_empty_reason_3")
    @gtin_empty_reason_3.setter
    def gtin_empty_reason_3(self, val): self._set_attr("gtin_empty_reason_3", val)
    @gtin_empty_reason_3.expression
    def gtin_empty_reason_3(cls): return sa.func.json_extract(cls.attributes_json, '$.gtin_empty_reason_3')

    @hybrid_property
    def gtin_entity_reason(self): return self._get_attr("gtin_entity_reason")
    @gtin_entity_reason.setter
    def gtin_entity_reason(self, val): self._set_attr("gtin_entity_reason", val)
    @gtin_entity_reason.expression
    def gtin_entity_reason(cls): return sa.func.json_extract(cls.attributes_json, '$.gtin_entity_reason')

    @hybrid_property
    def gtin_reason_lower(self): return self._get_attr("gtin_reason_lower")
    @gtin_reason_lower.setter
    def gtin_reason_lower(self, val): self._set_attr("gtin_reason_lower", val)
    @gtin_reason_lower.expression
    def gtin_reason_lower(cls): return sa.func.json_extract(cls.attributes_json, '$.gtin_reason_lower')

    @hybrid_property
    def gtin_empty_reason_typo(self): return self._get_attr("gtin_empty_reason_typo")
    @gtin_empty_reason_typo.setter
    def gtin_empty_reason_typo(self, val): self._set_attr("gtin_empty_reason_typo", val)
    @gtin_empty_reason_typo.expression
    def gtin_empty_reason_typo(cls): return sa.func.json_extract(cls.attributes_json, '$.gtin_empty_reason_typo')

    @hybrid_property
    def equipment(self): return self._get_attr("equipment")
    @equipment.setter
    def equipment(self, val): self._set_attr("equipment", val)
    @equipment.expression
    def equipment(cls): return sa.func.json_extract(cls.attributes_json, '$.equipment')

    @hybrid_property
    def measure(self): return self._get_attr("measure")
    @measure.setter
    def measure(self, val): self._set_attr("measure", val)
    @measure.expression
    def measure(cls): return sa.func.json_extract(cls.attributes_json, '$.measure')

    @hybrid_property
    def union_type(self): return self._get_attr("union_type")
    @union_type.setter
    def union_type(self, val): self._set_attr("union_type", val)
    @union_type.expression
    def union_type(cls): return sa.func.json_extract(cls.attributes_json, '$.union_type')

    @hybrid_property
    def allow_sales_without_stock(self): return self._get_attr("allow_sales_without_stock")
    @allow_sales_without_stock.setter
    def allow_sales_without_stock(self, val): self._set_attr("allow_sales_without_stock", val)
    @allow_sales_without_stock.expression
    def allow_sales_without_stock(cls): return sa.func.json_extract(cls.attributes_json, '$.allow_sales_without_stock')

    @hybrid_property
    def barcode(self): return self._get_attr("barcode")
    @barcode.setter
    def barcode(self, val): self._set_attr("barcode", val)
    @barcode.expression
    def barcode(cls): return sa.func.json_extract(cls.attributes_json, '$.barcode')

    @hybrid_property
    def branches(self): return self._get_attr("branches")
    @branches.setter
    def branches(self, val): self._set_attr("branches", val)
    @branches.expression
    def branches(cls): return sa.func.json_extract(cls.attributes_json, '$.branches')

    @hybrid_property
    def creation_date(self): return self._get_attr("creation_date")
    @creation_date.setter
    def creation_date(self, val): self._set_attr("creation_date", val)
    @creation_date.expression
    def creation_date(cls): return sa.func.json_extract(cls.attributes_json, '$.creation_date')

    @hybrid_property
    def variant_status(self): return self._get_attr("variant_status")
    @variant_status.setter
    def variant_status(self, val): self._set_attr("variant_status", val)
    @variant_status.expression
    def variant_status(cls): return sa.func.json_extract(cls.attributes_json, '$.variant_status')

    @hybrid_property
    def entity_key(self): return self._get_attr("entity_key")
    @entity_key.setter
    def entity_key(self, val): self._set_attr("entity_key", val)
    @entity_key.expression
    def entity_key(cls): return sa.func.json_extract(cls.attributes_json, '$.entity_key')

    @hybrid_property
    def unit_of_measure(self): return self._get_attr("unit_of_measure")
    @unit_of_measure.setter
    def unit_of_measure(self, val): self._set_attr("unit_of_measure", val)
    @unit_of_measure.expression
    def unit_of_measure(cls): return sa.func.json_extract(cls.attributes_json, '$.unit_of_measure')

# Alias for backward compatibility
RawEntity = UniversalEntity

class NormalizationRule(Base):
    __tablename__ = "normalization_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    field_name = Column(String, index=True) # e.g., "brand_lower"
    original_value = Column(String, index=True) # e.g., "mikrosoft"
    normalized_value = Column(String) # e.g., "Microsoft"
    is_regex = Column(Boolean, default=False)


class HarmonizationLog(Base):
    __tablename__ = "harmonization_logs"

    id = Column(Integer, primary_key=True, index=True)
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
    log_id = Column(Integer, index=True)
    record_id = Column(Integer, index=True)
    field = Column(String)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)


class StoreConnection(Base):
    __tablename__ = "store_connections"

    id = Column(Integer, primary_key=True, index=True)
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
    created_at       = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    confirmed_at     = Column(String, nullable=True)
    # Sprint 16 — scoring engine
    resolution_status = Column(String, default="unresolved", index=True)  # exact_match | probable_match | ambiguous | unresolved
    score_breakdown   = Column(Text, nullable=True)   # JSON: {identifiers, name, affiliation, coauthorship, topic}
    evidence          = Column(Text, nullable=True)   # JSON array of signal strings
    merged_sources    = Column(Text, nullable=True)   # JSON array of "source:id" refs merged into this record


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
    accent_color  = Column(String, default="#6366f1")   # indigo-500
    footer_text   = Column(String, default="Universal Knowledge Intelligence Platform")


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


# ── Sprint 61: Scheduled Imports ───────────────────────────────────────────────

class ScheduledImport(Base):
    """
    Cron-based automated ingestion from a configured store connection.
    interval_minutes is a simple interval approach (no full cron parser needed).
    """
    __tablename__ = "scheduled_imports"

    id              = Column(Integer, primary_key=True, index=True)
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

