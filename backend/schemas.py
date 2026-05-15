from datetime import datetime
from enum import Enum

import json
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from typing import Literal, Optional, List

class EntityBase(BaseModel):
    primary_label: Optional[str] = None
    secondary_label: Optional[str] = None
    canonical_id: Optional[str] = None
    entity_type: Optional[str] = None
    domain: Optional[str] = None
    validation_status: Optional[str] = None
    enrichment_doi: Optional[str] = None
    enrichment_citation_count: Optional[int] = 0
    enrichment_concepts: Optional[str] = None
    enrichment_source: Optional[str] = None
    enrichment_status: Optional[str] = "none"
    quality_score: Optional[float] = None

class Entity(EntityBase):
    id: int
    import_batch_id: Optional[int] = None
    attributes_json: Optional[str] = None
    normalized_json: Optional[str] = None
    source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


CATALOG_PORTAL_FACETS_DEFAULT = [
    "entity_type",
    "validation_status",
    "enrichment_status",
    "source",
]


class CatalogPortalBase(BaseModel):
    title: str
    slug: str
    description: Optional[str] = None
    source_batch_id: Optional[int] = None
    domain_id: str
    visibility: Literal["private", "org", "public"] = "private"
    source_label: Optional[str] = None
    source_context: dict = Field(default_factory=dict)
    search: Optional[str] = None
    min_quality: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ft_entity_type: Optional[str] = None
    ft_validation_status: Optional[str] = None
    ft_enrichment_status: Optional[str] = None
    ft_source: Optional[str] = None
    default_sort: Literal["id", "quality_score", "primary_label", "enrichment_status"] = "primary_label"
    default_order: Literal["asc", "desc"] = "asc"
    featured_facets: List[str] = Field(default_factory=lambda: list(CATALOG_PORTAL_FACETS_DEFAULT))


class CatalogPortalCreate(CatalogPortalBase):
    pass


class CatalogPortalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    source_batch_id: Optional[int] = None
    visibility: Optional[Literal["private", "org", "public"]] = None
    source_label: Optional[str] = None
    source_context: Optional[dict] = None
    search: Optional[str] = None
    min_quality: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ft_entity_type: Optional[str] = None
    ft_validation_status: Optional[str] = None
    ft_enrichment_status: Optional[str] = None
    ft_source: Optional[str] = None
    default_sort: Optional[Literal["id", "quality_score", "primary_label", "enrichment_status"]] = None
    default_order: Optional[Literal["asc", "desc"]] = None
    featured_facets: Optional[List[str]] = None


class CatalogPortalResponse(BaseModel):
    id: int
    org_id: Optional[int] = None
    title: str
    slug: str
    description: Optional[str] = None
    source_batch_id: Optional[int] = None
    domain_id: str
    visibility: str
    source_label: Optional[str] = None
    source_context: dict = Field(default_factory=dict)
    search: Optional[str] = None
    min_quality: Optional[float] = None
    ft_entity_type: Optional[str] = None
    ft_validation_status: Optional[str] = None
    ft_enrichment_status: Optional[str] = None
    ft_source: Optional[str] = None
    default_sort: str
    default_order: str
    featured_facets: List[str]
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CatalogPortalSummaryResponse(CatalogPortalResponse):
    summary: dict


class ImportBatchResponse(BaseModel):
    id: int
    org_id: Optional[int] = None
    domain_id: str
    source_type: str
    file_name: Optional[str] = None
    file_format: Optional[str] = None
    source_label: Optional[str] = None
    total_rows: int = 0
    entity_type_hint: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

class QualityDimension(BaseModel):
    weight: float
    contribution: float


class QualityBreakdown(BaseModel):
    entity_id: int
    score: float
    stored_score: Optional[float] = None
    breakdown: dict


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

    @field_validator("custom_headers")
    @classmethod
    def validate_custom_headers_json(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(f"custom_headers must be valid JSON: {e}") from e
        return v


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

    @field_validator("custom_headers")
    @classmethod
    def validate_custom_headers_json(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(f"custom_headers must be valid JSON: {e}") from e
        return v


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
    created_at:   Optional[str | datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def serialize_created_at(self, value: Optional[str | datetime]) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        return value


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
    resolution_route:  Optional[str]          = None
    complexity_score:  Optional[float]        = None
    review_required:   bool                   = False
    nil_reason:        Optional[str]          = None
    nil_score:         Optional[float]        = None
    hierarchy_distance: Optional[int]         = None
    reformulation_applied: bool               = False
    reformulation_gain: Optional[int]         = None
    reformulation_cost_estimate: Optional[float] = None
    reformulation_trace: Optional[dict]       = None

    model_config = ConfigDict(from_attributes=True)


class AuthorResolveRequest(BaseModel):
    field_name: str = Field(default="author_name", min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=500)
    context_affiliation: Optional[str] = Field(None, max_length=500)
    context_orcid_hint: Optional[str] = Field(None, max_length=25)
    context_doi: Optional[str] = Field(None, max_length=200)
    context_year: Optional[int] = Field(None, ge=1000, le=2100)
    resolve_affiliation: bool = True
    affiliation_field_name: str = Field(default="affiliation", min_length=1, max_length=64)


class AuthorityRecordLinkResponse(BaseModel):
    id: int
    source_authority_record_id: int
    target_authority_record_id: int
    link_type: str
    confidence: float
    status: str
    evidence: List[str]
    created_at: str
    confirmed_at: Optional[str] = None

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
    # Sprint 86 — resolve workflow + emoji reactions
    is_resolved:     bool = False
    resolved_at:     Optional[str] = None
    resolved_by_id:  Optional[int] = None
    emoji_reactions: dict = {}

    @field_validator("emoji_reactions", mode="before")
    @classmethod
    def _parse_emoji_reactions(cls, v):
        """Coerce the TEXT column JSON string to a dict."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        if v is None:
            return {}
        return v

    @field_validator("resolved_at", mode="before")
    @classmethod
    def _coerce_resolved_at(cls, v):
        """Convert DateTime objects to ISO string."""
        if v is None:
            return None
        if isinstance(v, str):
            return v
        # DateTime object
        return v.isoformat()


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
    favicon_url:   str
    accent_color:  str
    footer_text:   str


class BrandingSettingsUpdate(BaseModel):
    platform_name: Optional[str] = Field(None, min_length=1, max_length=80)
    logo_url:      Optional[str] = Field(None, max_length=500)
    favicon_url:   Optional[str] = Field(None, max_length=500)
    accent_color:  Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    footer_text:   Optional[str] = Field(None, max_length=200)


# ── Platform Authentication Settings ─────────────────────────────────────────

class PlatformAuthSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sso_enabled: bool
    sso_login_button_visible: bool
    sso_provider_label: str
    sso_auto_provision: bool
    sso_default_role: str
    sso_allowed_domains: str
    sso_provider_configured: bool = False


class PublicSsoSettingsResponse(BaseModel):
    sso_enabled: bool
    sso_login_button_visible: bool
    sso_provider_label: str
    sso_provider_configured: bool


class PlatformAuthSettingsUpdate(BaseModel):
    sso_enabled: Optional[bool] = None
    sso_login_button_visible: Optional[bool] = None
    sso_provider_label: Optional[str] = Field(None, min_length=1, max_length=80)
    sso_auto_provision: Optional[bool] = None
    sso_default_role: Optional[str] = Field(None, pattern=r"^(viewer|editor|admin)$")
    sso_allowed_domains: Optional[str] = Field(None, max_length=500)


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


class AnalysisContextUpdate(BaseModel):
    label:  Optional[str]  = Field(default=None, max_length=120)
    notes:  Optional[str]  = None
    pinned: Optional[bool] = None


class AnalysisContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:               int
    domain_id:        str
    user_id:          Optional[int]
    label:            str
    context_snapshot: str   # raw JSON string
    notes:            Optional[str]
    pinned:           bool
    created_at:       datetime


# ── Entity Relationship Graph ──────────────────────────────────────────────────

VALID_RELATION_TYPES = {"cites", "authored-by", "belongs-to", "related-to"}

class EntityRelationshipCreate(BaseModel):
    target_id:     int   = Field(..., ge=1)
    relation_type: str   = Field(..., max_length=50)
    weight:        float = Field(default=1.0, ge=0.0, le=10.0)
    notes:         str | None = Field(default=None, max_length=500)

    @field_validator("relation_type")
    @classmethod
    def validate_relation_type(cls, v: str) -> str:
        if v not in VALID_RELATION_TYPES:
            raise ValueError(f"relation_type must be one of {VALID_RELATION_TYPES}")
        return v


class EntityRelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:            int
    source_id:     int
    target_id:     int
    relation_type: str
    weight:        float
    notes:         str | None
    created_at:    datetime


class GraphNode(BaseModel):
    id:          int
    label:       str
    entity_type: str | None
    domain:      str | None
    is_center:   bool


class GraphEdge(BaseModel):
    id:            int
    source:        int
    target:        int
    relation_type: str
    weight:        float


class EntityGraphResponse(BaseModel):
    center_id: int
    depth:     int
    nodes:     list[GraphNode]
    edges:     list[GraphEdge]
