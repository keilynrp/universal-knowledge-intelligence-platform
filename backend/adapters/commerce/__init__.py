"""Commerce store adapters — Shopify, WooCommerce, Bsale, Custom API."""

from .base import BaseStoreAdapter, RemoteEntity
from .woocommerce import WooCommerceAdapter
from .shopify import ShopifyAdapter
from .bsale import BsaleAdapter
from .custom import CustomAPIAdapter


def get_commerce_adapter(platform: str, config: dict) -> BaseStoreAdapter:
    """Factory for commerce platform adapters."""
    adapters = {
        "woocommerce": WooCommerceAdapter,
        "shopify": ShopifyAdapter,
        "bsale": BsaleAdapter,
        "custom": CustomAPIAdapter,
    }
    adapter_class = adapters.get(platform)
    if not adapter_class:
        raise ValueError(f"Unsupported commerce platform: {platform}")
    return adapter_class(config)
