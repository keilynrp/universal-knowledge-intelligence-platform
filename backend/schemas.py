from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Optional, List

class EntityBase(BaseModel):
    entity_name: Optional[str] = None
    classification: Optional[str] = None
    entity_type: Optional[str] = None
    is_decimal_sellable: Optional[str] = None
    control_stock: Optional[str] = None
    status: Optional[str] = None
    taxes: Optional[str] = None
    variant: Optional[str] = None
    entity_code_universal_1: Optional[str] = None
    entity_code_universal_2: Optional[str] = None
    entity_code_universal_3: Optional[str] = None
    entity_code_universal_4: Optional[str] = None
    brand_lower: Optional[str] = None
    brand_capitalized: Optional[str] = None
    model: Optional[str] = None
    gtin: Optional[str] = None
    gtin_reason: Optional[str] = None
    gtin_empty_reason_1: Optional[str] = None
    gtin_empty_reason_2: Optional[str] = None
    gtin_empty_reason_3: Optional[str] = None
    gtin_entity_reason: Optional[str] = None
    gtin_reason_lower: Optional[str] = None
    gtin_empty_reason_typo: Optional[str] = None
    equipment: Optional[str] = None
    measure: Optional[str] = None
    union_type: Optional[str] = None
    allow_sales_without_stock: Optional[str] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None
    branches: Optional[str] = None
    creation_date: Optional[str] = None
    variant_status: Optional[str] = None
    entity_key: Optional[str] = None
    unit_of_measure: Optional[str] = None
    validation_status: Optional[str] = None
    
    # Enrichment fields
    enrichment_doi: Optional[str] = None
    enrichment_citation_count: int = 0
    enrichment_concepts: Optional[str] = None
    enrichment_source: Optional[str] = None
    enrichment_status: str = "none"

class Entity(EntityBase):
    id: int
    normalized_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class RuleBase(BaseModel):
    field_name: str
    original_value: str
    normalized_value: str
    is_regex: bool = False

class Rule(RuleBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class BulkRuleCreate(BaseModel):
    field_name: str
    canonical_value: str
    variations: List[str]


class HarmonizationChange(BaseModel):
    record_id: int
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None


class HarmonizationLogResponse(BaseModel):
    id: int
    step_id: str
    step_name: str
    records_updated: int
    fields_modified: List[str]
    executed_at: Optional[str] = None
    reverted: bool = False

    model_config = ConfigDict(from_attributes=True)


class UndoRedoResponse(BaseModel):
    log_id: int
    action: str
    records_restored: int
    step_id: str
    step_name: str


# ── Store Integration Schemas ─────────────────────────────────────────

_Platform = Literal["woocommerce", "shopify", "bsale", "custom"]
_SyncDirection = Literal["pull", "push", "bidirectional"]


class StoreConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    platform: _Platform
    base_url: str = Field(min_length=1, max_length=500)
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None
    custom_headers: Optional[str] = Field(default=None, max_length=5000)
    sync_direction: _SyncDirection = "bidirectional"
    notes: Optional[str] = None


class StoreConnectionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    platform: Optional[_Platform] = None
    base_url: Optional[str] = Field(default=None, min_length=1, max_length=500)
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None
    custom_headers: Optional[str] = Field(default=None, max_length=5000)
    is_active: Optional[bool] = None
    sync_direction: Optional[_SyncDirection] = None
    notes: Optional[str] = None


class StoreConnectionResponse(BaseModel):
    id: int
    name: str
    platform: str
    base_url: str
    is_active: bool
    last_sync_at: Optional[str] = None
    created_at: Optional[str] = None
    entity_count: int = 0
    sync_direction: str = "bidirectional"
    notes: Optional[str] = None
    # Credentials are intentionally excluded from responses

    model_config = ConfigDict(from_attributes=True)


# ── RBAC: Users ───────────────────────────────────────────────────────────

class UserRole(str, Enum):
    super_admin = "super_admin"
    admin       = "admin"
    editor      = "editor"
    viewer      = "viewer"


class UserCreate(BaseModel):
    username: str           = Field(min_length=3, max_length=50)
    email:    Optional[str] = Field(default=None, max_length=255)
    password: str           = Field(min_length=8, max_length=128)
    role:     UserRole      = UserRole.viewer


class UserUpdate(BaseModel):
    email:     Optional[str]      = Field(default=None, max_length=255)
    password:  Optional[str]      = Field(default=None, min_length=8, max_length=128)
    role:      Optional[UserRole] = None
    is_active: Optional[bool]     = None


class UserResponse(BaseModel):
    id:           int
    username:     str
    email:        Optional[str] = None
    role:         str
    is_active:    bool
    avatar_url:   Optional[str] = None
    display_name: Optional[str] = None
    bio:          Optional[str] = None
    created_at:   Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    """Self-service profile update — any authenticated user."""
    email:        Optional[str] = Field(default=None, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=100)
    bio:          Optional[str] = Field(default=None, max_length=500)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password:     str = Field(min_length=8, max_length=128)


# ── Authority Resolution Layer ────────────────────────────────────────────────

class AuthorityEntityType(str, Enum):
    general      = "general"
    person       = "person"
    organization = "organization"
    concept      = "concept"
    institution  = "institution"


class AuthorityResolveRequest(BaseModel):
    field_name:  str                = Field(min_length=1, max_length=64)
    value:       str                = Field(min_length=1, max_length=500)
    entity_type: AuthorityEntityType = AuthorityEntityType.general
    # Sprint 16 — optional contextual signals for the scoring engine
    context_affiliation: Optional[str] = Field(None, max_length=500)
    context_orcid_hint:  Optional[str] = Field(None, max_length=25)
    context_doi:         Optional[str] = Field(None, max_length=200)
    context_year:        Optional[int] = Field(None, ge=1000, le=2100)


class AuthorityRecordResponse(BaseModel):
    id:                int
    field_name:        str
    original_value:    str
    authority_source:  str
    authority_id:      str
    canonical_label:   str
    aliases:           List[str]
    description:       Optional[str] = None
    confidence:        float
    uri:               Optional[str] = None
    status:            str
    created_at:        str
    confirmed_at:      Optional[str] = None
    # Sprint 16 — scoring engine fields
    resolution_status: str                    = "unresolved"
    score_breakdown:   Optional[dict]         = None
    evidence:          Optional[List[str]]    = None
    merged_sources:    Optional[List[str]]    = None

    model_config = ConfigDict(from_attributes=True)


class AuthorityConfirmRequest(BaseModel):
    also_create_rule: bool = True


class BatchResolveRequest(BaseModel):
    field_name:    str                 = Field(min_length=1, max_length=64)
    entity_type:   AuthorityEntityType = AuthorityEntityType.general
    limit:         int                 = Field(default=20, ge=1, le=100)
    skip_existing: bool                = True


class BulkActionRequest(BaseModel):
    ids:              List[int] = Field(min_length=1, max_length=100)
    also_create_rules: bool     = True  # only relevant for bulk-confirm


# ── Webhooks ─────────────────────────────────────────────────────────────────

WEBHOOK_EVENTS = [
    "upload",
    "entity.update",
    "entity.delete",
    "entity.bulk_delete",
    "harmonization.apply",
    "authority.confirm",
    "authority.reject",
]

class WebhookCreate(BaseModel):
    url:    str       = Field(min_length=8, max_length=2048)
    events: List[str] = Field(min_length=1, max_length=20)
    secret: Optional[str] = Field(None, max_length=256)

class WebhookUpdate(BaseModel):
    url:       Optional[str]       = Field(None, min_length=8, max_length=2048)
    events:    Optional[List[str]] = Field(None, min_length=1, max_length=20)
    secret:    Optional[str]       = Field(None, max_length=256)
    is_active: Optional[bool]      = None

class WebhookResponse(BaseModel):
    id:                int
    url:               str
    events:            List[str]
    is_active:         bool
    created_at:        Optional[str] = None
    last_triggered_at: Optional[str] = None
    last_status:       Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ── Sprint 42: Annotations ────────────────────────────────────────────────────

class AnnotationCreate(BaseModel):
    entity_id:    Optional[int] = None
    authority_id: Optional[int] = None
    parent_id:    Optional[int] = None
    content:      str = Field(min_length=1, max_length=5000)


class AnnotationUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class AnnotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:           int
    entity_id:    Optional[int] = None
    authority_id: Optional[int] = None
    parent_id:    Optional[int] = None
    author_id:    int
    author_name:  str
    content:      str
    created_at:   datetime
    updated_at:   datetime


# ── Sprint 43: Notification Settings ─────────────────────────────────────────

class NotificationSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    smtp_host:                  str
    smtp_port:                  int
    smtp_user:                  str
    from_email:                 str
    recipient_email:            str
    enabled:                    bool
    notify_on_enrichment_batch: bool
    notify_on_authority_confirm: bool
    # smtp_password intentionally omitted


class NotificationSettingsUpdate(BaseModel):
    smtp_host:                   Optional[str]  = None
    smtp_port:                   Optional[int]  = Field(None, ge=1, le=65535)
    smtp_user:                   Optional[str]  = None
    smtp_password:               Optional[str]  = None   # plain; encrypted before storage
    from_email:                  Optional[str]  = None
    recipient_email:             Optional[str]  = None
    enabled:                     Optional[bool] = None
    notify_on_enrichment_batch:  Optional[bool] = None
    notify_on_authority_confirm: Optional[bool] = None


# ── Sprint 44: Branding Settings ─────────────────────────────────────────────

class BrandingSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform_name: str
    logo_url:      str
    accent_color:  str
    footer_text:   str


class BrandingSettingsUpdate(BaseModel):
    platform_name: Optional[str] = Field(None, min_length=1, max_length=80)
    logo_url:      Optional[str] = Field(None, max_length=500)
    accent_color:  Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    footer_text:   Optional[str] = Field(None, max_length=200)


# ── Phase 10 Sprint 45: Knowledge Gap Detector ───────────────────────────────

class GapItemResponse(BaseModel):
    category:      str
    severity:      str
    title:         str
    description:   str
    affected_count: int
    total_count:   int
    pct:           float
    action:        str


class GapReportResponse(BaseModel):
    domain_id:    str
    generated_at: datetime
    summary:      dict   # {"critical": N, "warning": N, "ok": N, "total_entities": N}
    gaps:         List[GapItemResponse]


# ── Phase 10 Sprint 46: Artifact Templates ────────────────────────────────────

VALID_SECTIONS = {
    "entity_stats",
    "enrichment_coverage",
    "top_brands",
    "topic_clusters",
    "harmonization_log",
}


class ArtifactTemplateCreate(BaseModel):
    name:          str       = Field(min_length=1, max_length=80)
    description:   str       = Field(default="", max_length=300)
    sections:      List[str] = Field(min_length=1)
    default_title: str       = Field(default="", max_length=120)

    @classmethod
    def model_post_init(cls, values):  # Pydantic v2 validator placeholder
        pass


class ArtifactTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:            int
    name:          str
    description:   str
    sections:      List[str]
    default_title: str
    is_builtin:    bool
    created_at:    datetime


# ── Phase 11 Sprint 48: Analysis Context Sessions ─────────────────────────────

class AnalysisContextCreate(BaseModel):
    domain_id: str         = Field(min_length=1, max_length=64)
    label:     str         = Field(default="", max_length=120)
    # context_snapshot is generated server-side; not accepted from client


class AnalysisContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:               int
    domain_id:        str
    user_id:          Optional[int]
    label:            str
    context_snapshot: str   # raw JSON string
    created_at:       datetime
