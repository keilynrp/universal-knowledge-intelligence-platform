import os
import logging
import yaml
from typing import List, Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DOMAINS_DIR = os.path.join(os.path.dirname(__file__), "domains")

class AttributeSchema(BaseModel):
    name: str             # db field name or arbitrary json key
    type: str             # string, integer, float, boolean, array
    label: str            # human-readable label
    required: bool = False
    is_core: bool = False # whether it matches standard RawEntity columns or goes into normalized_json


# ── Epistemology configuration models ─────────────────────────────────────────

class ParadigmIndicators(BaseModel):
    terms: List[str] = []
    document_types: List[str] = []
    journals_affinity: List[str] = []

class Paradigm(BaseModel):
    id: str
    label: str
    description: str = ""
    indicators: ParadigmIndicators = ParadigmIndicators()

class EvidenceLevel(BaseModel):
    level: int
    label: str
    weight: float = 1.0

class EpistemologyConfig(BaseModel):
    paradigms: List[Paradigm] = []
    evidence_hierarchy: List[EvidenceLevel] = []


# ── Discourse community configuration models ─────────────────────────────────

class HealthMetricDef(BaseModel):
    id: str
    label: str
    description: str = ""

class AuthoritySources(BaseModel):
    identity: List[str] = []
    bibliographic: List[str] = []
    institutional: List[str] = []

class ChannelTier(BaseModel):
    label: str
    description: str = ""
    auto_detect: bool = False
    manual_seeds: List[str] = []

class CommunicationChannels(BaseModel):
    tier_1: Optional[ChannelTier] = None
    tier_2: Optional[ChannelTier] = None
    tier_3: Optional[ChannelTier] = None

class ValidationPractice(BaseModel):
    id: str
    label: str
    weight: float = 1.0
    detectable: bool = False
    indicators: List[str] = []
    field: Optional[str] = None

class DiscourseConfig(BaseModel):
    authority_sources: Optional[AuthoritySources] = None
    communication_channels: Optional[CommunicationChannels] = None
    validation_practices: List[ValidationPractice] = []
    health_metrics: List[HealthMetricDef] = []


# ── Domain schema ─────────────────────────────────────────────────────────────

class DomainSchema(BaseModel):
    id: str
    name: str
    description: str
    primary_entity: str
    icon: Optional[str] = "Database"
    attributes: List[AttributeSchema]
    epistemology: Optional[EpistemologyConfig] = None
    discourse_community: Optional[DiscourseConfig] = None

class SchemaRegistry:
    def __init__(self):
        self.domains: Dict[str, DomainSchema] = {}
        self._load_registry()

    def _load_registry(self):
        self.domains.clear()
        if not os.path.exists(DOMAINS_DIR):
            os.makedirs(DOMAINS_DIR, exist_ok=True)
            
        for filename in os.listdir(DOMAINS_DIR):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(DOMAINS_DIR, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if data:
                            schema = DomainSchema(**data)
                            self.domains[schema.id] = schema
                except Exception as e:
                    logger.error("Error loading domain schema %s: %s", filename, e)

    def get_all_domains(self) -> List[DomainSchema]:
        # Return default first if available
        domains_list = list(self.domains.values())
        return sorted(domains_list, key=lambda d: 0 if d.id == "default" else 1)

    def get_domain(self, domain_id: str) -> Optional[DomainSchema]:
        return self.domains.get(domain_id)

    def save_domain(self, schema: DomainSchema) -> None:
        """Write schema to YAML and register it in memory."""
        filepath = os.path.join(DOMAINS_DIR, f"{schema.id}.yaml")
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(schema.model_dump(), f, allow_unicode=True,
                      default_flow_style=False, sort_keys=False)
        self.domains[schema.id] = schema

    def delete_domain(self, domain_id: str) -> bool:
        """Delete the YAML file and unregister. Returns False if not found."""
        filepath = os.path.join(DOMAINS_DIR, f"{domain_id}.yaml")
        if not os.path.exists(filepath):
            return False
        os.remove(filepath)
        self.domains.pop(domain_id, None)
        return True

    def is_builtin(self, domain_id: str) -> bool:
        return domain_id in _BUILTIN_DOMAIN_IDS


_BUILTIN_DOMAIN_IDS: frozenset = frozenset({"default", "science", "healthcare"})

registry = SchemaRegistry()
