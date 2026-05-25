"""
Base adapter interface for all store integrations.
Each platform adapter must implement these methods.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class RemoteEntity:
    """Normalized entity representation from any remote store."""
    remote_id: str
    name: str
    canonical_url: str
    sku: Optional[str] = None
    barcode: Optional[str] = None
    price: Optional[str] = None
    compare_at_price: Optional[str] = None
    stock: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = field(default_factory=list)
    images: Optional[List[str]] = field(default_factory=list)
    weight: Optional[str] = None
    dimensions: Optional[str] = None
    variants: Optional[List[dict]] = field(default_factory=list)
    raw_data: Optional[dict] = field(default_factory=dict)


@dataclass
class ConnectionTestResult:
    """Result of a connection test."""
    success: bool
    message: str
    store_name: Optional[str] = None
    entity_count: Optional[int] = None
    api_version: Optional[str] = None


class BaseStoreAdapter(ABC):
    """Abstract base class for all store platform adapters."""

    def __init__(self, config: dict):
        self.base_url = config.get("base_url", "").rstrip("/")
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")
        self.access_token = config.get("access_token")
        self.custom_headers = config.get("custom_headers")
        self.platform = config.get("platform", "unknown")

    @abstractmethod
    def test_connection(self) -> ConnectionTestResult:
        """Test that the connection credentials are valid."""
        pass

    @abstractmethod
    def fetch_entities(self, page: int = 1, per_page: int = 50) -> List[RemoteEntity]:
        """Fetch a page of entities from the remote store."""
        pass

    @abstractmethod
    def fetch_entity_by_id(self, remote_id: str) -> Optional[RemoteEntity]:
        """Fetch a single entity by its remote ID."""
        pass

    @abstractmethod
    def fetch_entity_count(self) -> int:
        """Get total number of entities in the store."""
        pass

    @abstractmethod
    def push_entity_update(self, remote_id: str, updates: dict) -> bool:
        """Push field updates to a remote entity. Returns True on success."""
        pass

    def get_canonical_url(self, entity_data: dict) -> str:
        """Build canonical URL from entity data. Override per platform if needed."""
        permalink = entity_data.get("permalink") or entity_data.get("url") or ""
        if permalink:
            return permalink
        slug = entity_data.get("slug") or entity_data.get("handle") or ""
        if slug:
            # We keep /product/ in the URL if the remote store uses it, 
            # but we can generalize the documentation.
            return f"{self.base_url}/product/{slug}"
        return ""
