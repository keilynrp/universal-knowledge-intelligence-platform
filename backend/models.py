from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float
from .database import Base

class RawEntity(Base):
    __tablename__ = "raw_entities"

    id = Column(Integer, primary_key=True, index=True)
    
    # Original Columns normalized to snake_case
    entity_name = Column(String, index=True) # Nombre del Producto
    classification = Column(String) # Clasificación
    entity_type = Column(String) # Tipo de Producto
    is_decimal_sellable = Column(String) # ¿Posible vender en cantidad decimal?
    control_stock = Column(String) # ¿Controlarás el stock del producto?
    status = Column(String, index=True) # Estado
    taxes = Column(String) # Impuestos
    variant = Column(String) # Variante
    
    # Messy ID definitions
    entity_code_universal_1 = Column(String) # Código universal de producto
    entity_code_universal_2 = Column(String) # Codigo universal
    entity_code_universal_3 = Column(String) # Codigo universal del producto
    entity_code_universal_4 = Column(String) # CODIGO UNIVERSAL DEL PRODRUCTO 
    
    brand_lower = Column(String) # marca
    brand_capitalized = Column(String, index=True) # Marca
    
    model = Column(String) # modelo
    
    # GTIN mess
    gtin = Column(String) # GTIN
    gtin_reason = Column(String) # Motivo de GTIN
    gtin_empty_reason_1 = Column(String) # Motivo de GTIN vacío
    gtin_empty_reason_2 = Column(String) # Motivo GTIN vacío 
    gtin_empty_reason_3 = Column(String) # Motivo GTIN vacia
    gtin_entity_reason = Column(String) # Motivo GTIN de producto
    gtin_reason_lower = Column(String) # motivo GTIN
    gtin_empty_reason_typo = Column(String) # Mtivo GTIN vacio
    
    equipment = Column(String) # EQUIMAPIENTO
    measure = Column(String) # MEDIDA
    union_type = Column(String) # TIPO DE UNION
    
    allow_sales_without_stock = Column(String) # ¿permitirás ventas sin stock?
    barcode = Column(String) # Código de Barras
    sku = Column(String, index=True) # SKU
    branches = Column(String) # Sucursales
    
    creation_date = Column(String) # Fecha de creacion
    variant_status = Column(String) # Estado Variante
    entity_key = Column(String) # Clave de producto
    unit_of_measure = Column(String) # Unidad de medida
    
    # Metadata
    validation_status = Column(String, default="pending", index=True) # pending, valid, invalid
    normalized_json = Column(Text, nullable=True) # Store clean version here

    # Scientometric Enrichment Fields
    enrichment_doi = Column(String, nullable=True)
    enrichment_citation_count = Column(Integer, default=0)
    enrichment_concepts = Column(Text, nullable=True) # Stored as comma-separated
    enrichment_source = Column(String, nullable=True)
    enrichment_status = Column(String, default="none", index=True) # none, pending, completed, failed

    # Data provenance
    source = Column(String, default="user")  # "user" | "demo" | adapter name

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
    action      = Column(String, index=True)          # e.g. "upload", "entity.delete", "harmonization.apply"
    entity_type = Column(String, nullable=True)       # "entity", "authority_record", "rule", …
    entity_id   = Column(Integer, nullable=True)
    user_id     = Column(Integer, nullable=True)
    details     = Column(Text, nullable=True)         # JSON blob with extra context
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
