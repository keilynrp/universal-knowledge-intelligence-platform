from .base import BaseStoreAdapter
from .commerce import (
    WooCommerceAdapter,
    ShopifyAdapter,
    BsaleAdapter,
    CustomAPIAdapter,
    get_commerce_adapter,
)
# Re-export commerce submodules for backward-compatible `from backend.adapters import shopify`
from .commerce import shopify, woocommerce, bsale, custom  # noqa: F401


def get_adapter(platform: str, config: dict) -> BaseStoreAdapter:
    """Factory function to get the right adapter for a platform."""
    return get_commerce_adapter(platform, config)
