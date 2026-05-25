"""
Shopify Admin REST API adapter.
Docs: https://shopify.dev/docs/api/admin-rest
"""
import logging
import requests
from typing import List, Optional

from .base import BaseStoreAdapter, RemoteEntity, ConnectionTestResult

logger = logging.getLogger(__name__)


class ShopifyAdapter(BaseStoreAdapter):

    def __init__(self, config: dict):
        super().__init__(config)
        # Shopify uses access token in header
        self.api_version = "2024-01"
        self.api_base = f"{self.base_url}/admin/api/{self.api_version}"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token or "",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, params: dict = None, json_data: dict = None, timeout: int = 30):
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        try:
            resp = requests.request(
                method, url,
                headers=self.headers,
                params=params,
                json=json_data,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Cannot connect to {self.base_url}: {e}")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Shopify API error ({resp.status_code}): {resp.text[:300]}")
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Request to {url} timed out after {timeout}s")

    def test_connection(self) -> ConnectionTestResult:
        try:
            resp = self._request("GET", "shop.json")
            data = resp.json()
            shop = data.get("shop", {})
            return ConnectionTestResult(
                success=True,
                message="Connected successfully to Shopify",
                store_name=shop.get("name", self.base_url),
                entity_count=None,
                api_version=f"Shopify {self.api_version}",
            )
        except Exception as e:
            return ConnectionTestResult(success=False, message=str(e))

    def _parse_entity(self, item: dict) -> RemoteEntity:
        images = [img.get("src", "") for img in item.get("images", []) if img.get("src")]
        tags = [t.strip() for t in (item.get("tags", "") or "").split(",") if t.strip()]

        # Get first variant data
        first_variant = item.get("variants", [{}])[0] if item.get("variants") else {}
        variants = [{
            "id": str(v.get("id", "")),
            "sku": v.get("sku", ""),
            "price": v.get("price", ""),
            "stock": str(v.get("inventory_quantity", "")),
            "title": v.get("title", ""),
        } for v in item.get("variants", [])]

        handle = item.get("handle", "")
        canonical = f"{self.base_url}/products/{handle}" if handle else ""

        return RemoteEntity(
            remote_id=str(item["id"]),
            name=item.get("title", ""),
            canonical_url=canonical,
            sku=first_variant.get("sku", ""),
            barcode=first_variant.get("barcode", ""),
            price=first_variant.get("price", ""),
            compare_at_price=first_variant.get("compare_at_price", ""),
            stock=str(first_variant.get("inventory_quantity", "")) if first_variant.get("inventory_quantity") is not None else None,
            status=item.get("status", ""),
            description=item.get("body_html", ""),
            short_description=None,
            brand=item.get("vendor", ""),
            category=item.get("entity_type", ""),
            tags=tags,
            images=images,
            weight=str(first_variant.get("weight", "")),
            dimensions=None,
            variants=variants,
            raw_data=item,
        )

    def fetch_entities(self, page: int = 1, per_page: int = 50) -> List[RemoteEntity]:
        # Shopify uses cursor-based pagination; for simplicity we use limit
        resp = self._request("GET", "products.json", params={"limit": per_page})
        data = resp.json()
        items = data.get("products", [])
        return [self._parse_entity(item) for item in items]

    def fetch_entity_by_id(self, remote_id: str) -> Optional[RemoteEntity]:
        try:
            resp = self._request("GET", f"products/{remote_id}.json")
            data = resp.json()
            return self._parse_entity(data.get("product", {}))
        except Exception as exc:
            logger.warning("Shopify fetch_entity_by_id(%s) failed: %s", remote_id, exc)
            return None

    def fetch_entity_count(self) -> int:
        try:
            resp = self._request("GET", "products/count.json")
            return resp.json().get("count", 0)
        except Exception as exc:
            logger.warning("Shopify fetch_entity_count failed: %s", exc)
            return 0

    def push_entity_update(self, remote_id: str, updates: dict) -> bool:
        remote_payload: dict = {}
        if "name" in updates:
            remote_payload["title"] = updates["name"]
        if "description" in updates:
            remote_payload["body_html"] = updates["description"]
        if "status" in updates:
            remote_payload["status"] = updates["status"]
        if "brand" in updates:
            remote_payload["vendor"] = updates["brand"]
        if "category" in updates:
            remote_payload["entity_type"] = updates["category"]
        if "tags" in updates:
            remote_payload["tags"] = ", ".join(updates["tags"]) if isinstance(updates["tags"], list) else updates["tags"]

        # Variant-level updates
        variant_updates: dict = {}
        if "sku" in updates:
            variant_updates["sku"] = updates["sku"]
        if "price" in updates:
            variant_updates["price"] = updates["price"]
        if "barcode" in updates:
            variant_updates["barcode"] = updates["barcode"]

        try:
            if remote_payload:
                self._request("PUT", f"products/{remote_id}.json", json_data={"product": remote_payload})
            if variant_updates:
                # Get first variant ID
                product_resp = self._request("GET", f"products/{remote_id}.json")
                product_data = product_resp.json().get("product", {})
                first_variant = (product_data.get("variants") or [{}])[0]
                variant_id = first_variant.get("id")
                if variant_id:
                    self._request("PUT", f"variants/{variant_id}.json", json_data={"variant": variant_updates})
            return True
        except Exception as exc:
            logger.warning("Shopify push_entity_update(%s) failed: %s", remote_id, exc)
            return False
